import json
import pytest
from verifier.connectors import parse_feed,x_event,Outbox
from verifier import network

def test_x_author_and_edits_keep_stable_content_identity():
    value=x_event({'data':{'id':'102','text':'Short text','note_tweet':{'text':'The complete long post'},'author_id':'42','edit_history_tweet_ids':['101','102'],'lang':'en'}})
    assert value['content_id']=='101' and value['revision']==2 and value['event_type']=='edited'
    assert value['author_verified'] and value['author_ref']=='42' and value['text']=='The complete long post'
    assert not value['allow_external_processing'] and not value['allow_web_search']

@pytest.mark.parametrize('xml',[
    '<rss><channel><item><guid>id1</guid><title>A claim</title><description>&lt;b&gt;Body&lt;/b&gt;</description><link>https://example.com/post</link></item></channel></rss>',
    '<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>id1</id><title>A claim</title><summary>Body</summary><link href="https://example.com/post"/></entry></feed>'
])
def test_rss_and_atom_normalization(xml):
    values=parse_feed(xml,'https://example.com/feed')
    assert len(values)==1 and values[0]['text']=='A claim\n\nBody' and values[0]['source_url']=='https://example.com/post'

def test_entity_expansion_rejected():
    with pytest.raises(ValueError): parse_feed('<!DOCTYPE x [<!ENTITY y SYSTEM "file:///etc/passwd">]><rss>&y;</rss>','https://example.com')

@pytest.mark.asyncio
async def test_rss_changes_dedupe_and_delivery_survives_restart(tmp_path,monkeypatch):
    path=tmp_path/'outbox.db'
    entry={'id':'one','text':'Original claim','source_url':'https://example.com/post','author_ref':'example.com'}
    box=Outbox(path)
    assert box.rss(entry) and not box.rss(entry)
    assert box.rss({**entry,'text':'Edited claim'})
    assert box.rss(entry)  # A -> B -> A is a new revision, not an old event replay.
    box.db.close(); box=Outbox(path)
    rows=box.db.execute('SELECT * FROM deliveries').fetchall()
    assert [json.loads(row['body'])['revision'] for row in rows]==[1,2,3]
    delivered=[]
    async def request(*args,**kwargs):
        delivered.append(kwargs['body'])
        return 202,{},b'{"case_id":"case","duplicate":false}'
    monkeypatch.setattr(network,'request',request)
    assert await box.deliver('http://127.0.0.1:8791','test-token')==3
    assert len(delivered)==3 and all(not item['author_verified'] for item in delivered)
    assert all(row['body']=='' for row in box.db.execute('SELECT * FROM deliveries'))
    assert await box.deliver('http://127.0.0.1:8791','test-token')==0
    box.db.close()

@pytest.mark.asyncio
async def test_rejected_intake_keeps_durable_event(tmp_path,monkeypatch):
    box=Outbox(tmp_path/'outbox.db')
    box.enqueue({'event_id':'a','content_id':'b','text':'A test claim'})
    async def request(*args,**kwargs): return 401,{},b'{}'
    monkeypatch.setattr(network,'request',request)
    with pytest.raises(RuntimeError): await box.deliver('http://127.0.0.1:8791','revoked-token')
    assert box.db.execute("SELECT COUNT(*) FROM deliveries WHERE status='pending'").fetchone()[0]==1
    box.db.close()
