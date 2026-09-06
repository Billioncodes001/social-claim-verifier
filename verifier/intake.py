"""Shared, transactional event intake for platform feeds and the demo."""
import hashlib
import json
from fastapi import HTTPException
from .db import dumps, uid, now
from .network import validate_url, NetworkError
from .configuration import profile, queue_limit, workspace_config

def enqueue(db, body, actor, demo_owner=None):
    config = profile(db, body.platform)
    if body.event_type != 'deleted' and not config['enabled']:
        raise HTTPException(403, 'This platform is disabled in this workspace')
    if (body.allow_external_processing and not config['allow_hosted']) or (body.allow_web_search and not config['allow_search']):
        raise HTTPException(403, 'This platform profile does not permit the requested external processing or search')
    if body.content_id.startswith('demo:') and not demo_owner:
        raise HTTPException(403, 'Demo content can only be managed through the demo API')
    if body.event_type != 'deleted' and not body.text:
        raise HTTPException(422, 'Submit the post text. Private or dynamic social URLs cannot be read as a substitute.')
    for url in body.evidence_urls + ([body.source_url] if body.source_url else []):
        try:
            validate_url(url)
        except NetworkError as exc:
            raise HTTPException(422, str(exc)) from None
    content = body.model_dump()
    if content.get('posted_at') is None:
        content.pop('posted_at', None)
    # Browser users cannot assert platform-confirmed author identity.
    if actor['role'] != 'ingest' or demo_owner:
        content['author_verified'] = False
    encoded = dumps(content)
    fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
    with db.connect() as tx:
        tx.execute('BEGIN IMMEDIATE')
        existing = tx.execute('SELECT * FROM events WHERE event_id=?', (body.event_id,)).fetchone()
        if existing:
            if existing['digest'] != fingerprint:
                raise HTTPException(409, 'Event ID already used for different content')
            return {'case_id': existing['case_id'], 'duplicate': True}
        latest = tx.execute('SELECT * FROM cases WHERE platform=? AND content_id=? ORDER BY revision DESC LIMIT 1', (body.platform, body.content_id)).fetchone()
        if latest and body.revision <= latest['revision']:
            raise HTTPException(409, 'Content revision must increase; stale or duplicate revision rejected')
        if demo_owner and latest and latest['owner_id'] != demo_owner:
            raise HTTPException(403, 'Demo content belongs to another user')
        if demo_owner and body.event_type != 'deleted':
            used = tx.execute("SELECT COUNT(*) FROM cases WHERE is_demo=1 AND owner_id=? AND created>=? AND json_extract(input,'$.event_type')!='deleted'", (demo_owner, now()[:10])).fetchone()[0]
            if used >= workspace_config(db)['demo_daily_limit']:
                raise HTTPException(429, 'Daily demo investigation limit reached. Try again after midnight UTC.')
        if body.event_type != 'deleted' and tx.execute("SELECT COUNT(*) FROM cases WHERE status IN ('queued','processing')").fetchone()[0] >= queue_limit():
            raise HTTPException(429, 'Queue is full. Retry later with the same event ID.')
        if latest:
            tx.execute("UPDATE cases SET status='superseded',stage='Replaced by a newer revision',updated=? WHERE platform=? AND content_id=? AND status!='deleted'", (now(), body.platform, body.content_id))
        if body.event_type == 'deleted':
            older = tx.execute('SELECT id,input FROM cases WHERE platform=? AND content_id=?', (body.platform, body.content_id)).fetchall()
            for old in older:
                retained = json.loads(old['input'])
                retained.update(text='', evidence_urls=[], source_url='', author_ref='', author_verified=False)
                tx.execute("UPDATE cases SET status='deleted',stage='Content removed',input=?,result=NULL,error=NULL,author_ref='',author_verified=0,updated=? WHERE id=?", (dumps(retained), now(), old['id']))
                tx.execute('DELETE FROM runs WHERE case_id=?', (old['id'],))
                tx.execute('DELETE FROM reviews WHERE case_id=?', (old['id'],))
                tx.execute("UPDATE audit SET details='{}' WHERE subject=?", (old['id'],))
            content.update(text='', evidence_urls=[], source_url='', author_ref='', author_verified=False)
            encoded = dumps(content)
        case_id, stamp = uid(), now()
        state = 'deleted' if body.event_type == 'deleted' else 'queued'
        tx.execute('INSERT INTO cases(id,platform,content_id,revision,author_ref,author_verified,status,stage,input,created,updated,is_demo,owner_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (case_id, body.platform, body.content_id, body.revision, content['author_ref'], content['author_verified'], state, 'Deleted' if state == 'deleted' else 'Waiting for agents', encoded, stamp, stamp, int(bool(demo_owner)), demo_owner))
        tx.execute('INSERT INTO events VALUES(?,?,?)', (body.event_id, fingerprint, case_id))
    db.audit(actor['username'], 'content.'+body.event_type, case_id, {'platform': body.platform, 'revision': body.revision})
    return {'case_id': case_id, 'duplicate': False}
