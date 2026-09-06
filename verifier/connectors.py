"""Runnable source adapters with a durable local delivery queue.

The X adapter consumes a customer's existing filtered-stream rules. It does not
create platform permissions, post replies, modify accounts, or evade login.
"""
import argparse
import asyncio
import hashlib
import json
import os
import sqlite3
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit, urljoin
import httpx
from bs4 import BeautifulSoup
from . import network
from .models import ContentInput
from .db import dumps, now

def fingerprint(value):
    return hashlib.sha256(value.encode()).hexdigest()

def x_event(message, allow_external=False, allow_search=False):
    post=message.get('data', {})
    if not post.get('id') or not post.get('text'):
        raise ValueError('Stream message has no post content')
    history=post.get('edit_history_tweet_ids') or [post['id']]
    if post['id'] not in history:
        raise ValueError('Post edit history is inconsistent')
    revision=history.index(post['id'])+1
    text=(post.get('note_tweet') or {}).get('text') or post['text']
    return ContentInput(event_id='x:'+post['id'],platform='x',content_id=history[0],revision=revision,
        event_type='edited' if revision>1 else 'created',text=text,author_ref=post.get('author_id',''),
        author_verified=bool(post.get('author_id')),source_url='https://x.com/i/status/'+post['id'],
        allow_external_processing=allow_external,allow_web_search=allow_search,language=post.get('lang','en')).model_dump()

def parse_feed(xml, feed_url, limit=20):
    if len(xml)>2_000_000 or '<!doctype' in xml.lower() or '<!entity' in xml.lower():
        raise ValueError('Feed declarations or size are not permitted')
    try:
        root=ET.fromstring(xml)
    except ET.ParseError:
        raise ValueError('Source is not valid RSS/Atom XML') from None
    nodes=list(root.iter())
    if len(nodes)>15000: raise ValueError('Feed has too many XML nodes')
    local=lambda tag: tag.rsplit('}',1)[-1]
    entries=[item for item in nodes if local(item.tag) in ('item','entry')][:limit]
    result=[]
    for entry in entries:
        fields={local(child.tag):child for child in entry}
        def text(name):
            value=fields.get(name)
            return ''.join(value.itertext()).strip() if value is not None else ''
        linknode=fields.get('link')
        link=(linknode.get('href','') if linknode is not None else '') or text('link')
        link=urljoin(feed_url,link)
        if urlsplit(link).scheme not in ('http','https'): link=''
        identity=text('guid') or text('id') or link or text('title')
        body=text('encoded') or text('content') or text('description') or text('summary')
        plain=' '.join(BeautifulSoup(body,'html.parser').get_text(' ',strip=True).split())
        title=text('title')
        content=title + ('\n\n'+plain if plain and plain!=title else '')
        if not identity or not content.strip(): continue
        if len(content)>16000: raise ValueError('Feed entry exceeds the text budget; use a complete claim excerpt')
        result.append({'id':fingerprint(feed_url+'\n'+identity),'text':content,'source_url':link,'author_ref':urlsplit(feed_url).hostname or ''})
    return result

class Outbox:
    def __init__(self,path):
        path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path)
        self.db.row_factory=sqlite3.Row
        self.db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS deliveries(event_id TEXT PRIMARY KEY,body TEXT NOT NULL,digest TEXT NOT NULL,status TEXT NOT NULL,case_id TEXT,created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS rss_items(id TEXT PRIMARY KEY,digest TEXT NOT NULL,revision INTEGER NOT NULL);
        ''')

    def enqueue(self,event):
        body=dumps(ContentInput.model_validate(event).model_dump())
        existing=self.db.execute('SELECT digest FROM deliveries WHERE event_id=?',(event['event_id'],)).fetchone()
        if existing:
            if existing['digest']!=fingerprint(body): raise ValueError('Conflicting event ID in connector outbox')
            return False
        if self.db.execute("SELECT COUNT(*) FROM deliveries WHERE status='pending'").fetchone()[0]>=10000:
            raise RuntimeError('Connector delivery queue is full; resolve intake errors before continuing')
        self.db.execute("INSERT INTO deliveries VALUES(?,?,?,'pending',NULL,?)",(event['event_id'],body,fingerprint(body),now()))
        self.db.commit()
        return True

    def rss(self,entry,allow_external=False,allow_search=False):
        signature=fingerprint(dumps(entry))
        existing=self.db.execute('SELECT * FROM rss_items WHERE id=?',(entry['id'],)).fetchone()
        if existing and existing['digest']==signature: return False
        revision=existing['revision']+1 if existing else 1
        event=ContentInput(event_id=f"rss:{entry['id']}:{revision}",platform='rss',content_id=entry['id'],revision=revision,
            event_type='edited' if revision>1 else 'created',text=entry['text'],source_url=entry['source_url'],
            author_ref=entry['author_ref'],author_verified=False,allow_external_processing=allow_external,allow_web_search=allow_search).model_dump()
        # If interrupted between these writes, replay finds the same durable event.
        self.enqueue(event)
        self.db.execute('INSERT INTO rss_items VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET digest=excluded.digest,revision=excluded.revision',(entry['id'],signature,revision))
        self.db.commit()
        return True

    async def deliver(self,base_url,token):
        parts=network.validate_url(base_url)
        local=parts.hostname in ('127.0.0.1','localhost','::1')
        if not local and parts.scheme!='https': raise ValueError('Remote intake endpoints require HTTPS')
        if parts.query or parts.fragment: raise ValueError('Intake URL must not contain query strings or fragments')
        count=0
        for row in self.db.execute("SELECT * FROM deliveries WHERE status='pending' ORDER BY created LIMIT 100").fetchall():
            for attempt in range(3):
                try:
                    status,_,raw=await network.request('POST',base_url.rstrip('/')+'/api/content-events',body=json.loads(row['body']),
                        headers={'Authorization':'Bearer '+token},local=local,timeout=25)
                except network.NetworkError:
                    if attempt==2: raise RuntimeError('Intake unavailable. Pending events remain in the local outbox.') from None
                    await asyncio.sleep(2**attempt); continue
                if status==202:
                    response=json.loads(raw)
                    self.db.execute("UPDATE deliveries SET status='delivered',body='',case_id=? WHERE event_id=?",(response['case_id'],row['event_id']))
                    self.db.commit(); count+=1; break
                if status in (429,500,502,503,504) and attempt<2:
                    await asyncio.sleep(2**attempt); continue
                raise RuntimeError(f'Intake returned HTTP {status}; pending events retained. Check token, revisions and queue capacity.')
        return count

async def watch_rss(args,outbox,token):
    while True:
        await outbox.deliver(args.url,token)
        _,xml,_=await network.fetch(args.feed)
        entries=parse_feed(xml,args.feed,args.limit)
        added=sum(outbox.rss(entry,args.allow_external,args.allow_search) for entry in entries)
        delivered=await outbox.deliver(args.url,token)
        print(f'RSS: {len(entries)} entries read; {added} new revisions; {delivered} delivered.',flush=True)
        if args.once: return
        await asyncio.sleep(max(60,args.interval))

async def watch_x(args,outbox,token):
    bearer=os.environ.get('X_BEARER_TOKEN','')
    if not bearer: raise ValueError('Set X_BEARER_TOKEN to the customer-authorized X API credential')
    delay=5
    while True:
        await outbox.deliver(args.url,token)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(35,connect=15),trust_env=False) as client:
                async with client.stream('GET','https://api.x.com/2/tweets/search/stream',
                    params={'tweet.fields':'author_id,created_at,lang,edit_history_tweet_ids,note_tweet'},headers={'Authorization':'Bearer '+bearer}) as response:
                    if response.status_code in (401,403): raise ValueError('X denied access. Check the API credential and subscription.')
                    if response.status_code!=200: raise RuntimeError(f'X stream returned HTTP {response.status_code}')
                    print('X stream connected to your existing filter rules.',flush=True)
                    buffer=bytearray()
                    async for chunk in response.aiter_bytes():
                        buffer.extend(chunk)
                        if len(buffer)>500000: raise RuntimeError('X stream frame exceeds the input budget')
                        while b'\n' in buffer:
                            line,_,remainder=buffer.partition(b'\n'); buffer=bytearray(remainder)
                            if not line.strip(): continue
                            message=json.loads(line)
                            if 'data' not in message: continue
                            outbox.enqueue(x_event(message,args.allow_external,args.allow_search))
                            await outbox.deliver(args.url,token)
                            delay=5
        except (httpx.HTTPError,network.NetworkError,RuntimeError) as exc:
            print(f'{type(exc).__name__}: reconnecting after {delay}s; pending deliveries retained.',flush=True)
            await asyncio.sleep(delay); delay=min(delay*2,300)

def main():
    parser=argparse.ArgumentParser(description='Monitor authorized content and deliver it to Claim Verifier')
    parser.add_argument('source',choices=['rss','x','jsonl','drain'])
    parser.add_argument('--url',default='http://127.0.0.1:8791')
    parser.add_argument('--state',default='.runtime/connector.sqlite3')
    parser.add_argument('--feed')
    parser.add_argument('--file')
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--limit',type=int,default=20)
    parser.add_argument('--interval',type=int,default=300)
    parser.add_argument('--allow-external',action='store_true')
    parser.add_argument('--allow-search',action='store_true')
    args=parser.parse_args()
    token=os.environ.get('VERIFIER_INGEST_TOKEN','')
    if not token: parser.error('Set VERIFIER_INGEST_TOKEN to a token created in Integrations')
    if args.source=='rss' and (not args.feed or not 1<=args.limit<=50): parser.error('RSS needs --feed and --limit between 1 and 50')
    outbox=Outbox(args.state)
    try:
        if args.source=='rss': asyncio.run(watch_rss(args,outbox,token))
        elif args.source=='x': asyncio.run(watch_x(args,outbox,token))
        else:
            if args.source=='jsonl':
                if not args.file: parser.error('JSONL ingestion requires --file')
                with open(args.file,encoding='utf-8') as handle:
                    for line in handle:
                        if len(line)>150000: raise ValueError('Input event exceeds the size budget')
                        if line.strip(): outbox.enqueue(json.loads(line))
            print('Delivered:',asyncio.run(outbox.deliver(args.url,token)))
    except (ValueError,RuntimeError,network.NetworkError) as exc:
        parser.exit(1,str(exc)+'\n')
    except KeyboardInterrupt:
        print('Monitor stopped. Pending events are saved for restart.')
    finally:
        outbox.db.close()

if __name__=='__main__': main()
