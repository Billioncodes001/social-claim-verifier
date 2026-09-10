"""Isolated browser-test backend. Synthetic accounts and evidence; never production data."""
import json
import os
from pathlib import Path
import tempfile
import time
import uvicorn
from verifier.app import create_app
from verifier.db import dumps, now
from verifier.models import ContentInput, MonitorInput
from verifier.intake import enqueue
from verifier.security import hash_password
from verifier.review_export import text_hash
from datetime import datetime, timezone, timedelta


def make_test_app(root):
    app=create_app(root,run_workers=False)
    db,vault=app.state.db,app.state.vault
    db.execute('INSERT INTO users VALUES(?,?,?,?)',('browser-owner','owner',hash_password('browser-fixture-password'),'admin'))
    db.execute('INSERT INTO users VALUES(?,?,?,?)',('browser-reviewer','reviewer',hash_password('browser-fixture-password'),'reviewer'))
    actor={'id':'browser-owner','username':'owner','role':'admin'}
    identifier=enqueue(db,ContentInput(event_id='browser-seed',content_id='browser-seed',platform='manual',text='Apollo 11 first landed humans on the Moon in 1972.'),actor,demo_owner=actor['id'])['case_id']
    quote='Apollo 11 landed on the Moon on July 20, 1969.'
    result={'claims':[{'id':'C1','text':'Apollo 11 first landed humans on the Moon in 1972.','context':'A test claim','quote':'Apollo 11 first landed humans on the Moon in 1972.','checkable':True}],
            'judgments':[{'claim_id':'C1','verdict':'contradicted','rationale':'The fixture record gives 1969, not 1972. This synthetic assessment exercises the review interface.',
                          'citations':[{'evidence_id':'E1','quote':quote}],'citation_check':'normalized_quote_match'}],
            'evidence':[{'id':'E1','url':'https://www.nasa.gov/mission/apollo-11/','title':'Apollo 11 — browser test fixture','status':'retrieved','text':quote,'host':'www.nasa.gov','retrieved_at':now(),'sha256':'f'*64}],
            'limitations':['Synthetic browser fixture; not a live factual evaluation.'],'elapsed_ms':12500}
    db.execute("UPDATE cases SET status='needs_review',stage='Ready for review',result=? WHERE id=?",(dumps(result),identifier))
    # Dedicated local-only source revisions for the freshness/export workflow.
    for revision, text in [(1, 'Synthetic source capture before a local revision.'), (2, 'Synthetic source capture after a local revision.')]:
        review_id = enqueue(db, ContentInput(event_id=f'freshness-{revision}', content_id='freshness-example',
            revision=revision, event_type='created' if revision == 1 else 'edited',
            text='Synthetic freshness review example.'), actor, demo_owner=actor['id'])['case_id']
        captured = json.loads(dumps(result))
        captured['evidence'] = [{'id': 'E1', 'url': 'https://evidence.example.test/local-record', 'title': 'Synthetic source revision',
            'status': 'retrieved', 'text': text, 'sha256': text_hash(text), 'host': 'evidence.example.test',
            'retrieved_at': (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()}]
        captured['judgments'] = [{'claim_id': 'C1', 'verdict': 'unresolved', 'rationale': 'Synthetic fixture: no validated factual conclusion.', 'citations': []}]
        captured['claims'] = [{'id': 'C1', 'text': 'Synthetic freshness review example.', 'context': 'Local test', 'quote': 'Synthetic freshness review example.', 'checkable': True}]
        db.execute("UPDATE cases SET status='needs_review',stage='Ready for review',result=? WHERE id=?", (dumps(captured), review_id))
    for index,role in enumerate(('extractor','analyst','challenger','adjudicator')):
        db.execute("INSERT INTO runs(id,case_id,role,status,model,output,elapsed_ms,created) VALUES(?,?,?,'complete','browser-fixture',?,?,?)",(role,identifier,role,dumps({'fixture':True}),1000+index,now()))
    db.set_setting('social_app:x',{'client_id':'browser-fixture-app','secret':vault.encrypt('fixture-app-secret'),'graph_version':'','revision':'fixture-revision'})
    db.execute("INSERT INTO social_accounts(id,owner_id,provider,remote_id,display_name,secret,expires,scopes,status,monitor,next_poll) VALUES(?,?,'x','42','Fixture X account',?,?,?,'active',?,?)",('fixture-account',actor['id'],vault.encrypt(dumps({'access_token':'fixture-read-token'})),time.time()+86400,'tweet.read users.read',dumps(MonitorInput().model_dump()),time.time()+86400))
    async def fixture_call(method,url,**kwargs):
        return {'data':[{'id':'123456789','text':'Browser fixture: a newly discovered claim for review.','created_at':'2026-09-06T12:00:00Z'}]}
    app.state.social.call=fixture_call
    return app


if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='claim-verifier-browser-') as temporary:
        uvicorn.run(make_test_app(Path(temporary)),host='127.0.0.1',port=int(os.environ.get('VERIFIER_UI_TEST_PORT','8793')),access_log=False)
