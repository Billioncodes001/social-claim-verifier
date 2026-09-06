import json
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from verifier.db import uid, now, dumps
from verifier.security import hash_password
from verifier.policy import account_state
from conftest import ingest, assessed

def test_auth_setup_and_cookie_boundaries(workspace):
    app, client = workspace
    with TestClient(app) as anonymous:
        assert anonymous.get('/api/cases').status_code == 401
        assert anonymous.post('/api/auth/setup', json={'username':'second','password':'another-good-password'}).status_code == 409
    assert client.get('/').status_code == 200
    assert "frame-ancestors 'none'" in client.get('/').headers['content-security-policy']
    assert client.post('/api/tokens',json={'name':'bad origin'},headers={'Origin':'https://attacker.example'}).status_code == 403
    assert client.post('/api/tokens',content='x'*150001).status_code == 413
    assert client.get('/api/auth/status',headers={'Host':'attacker.example'}).status_code == 400

def test_reviewer_cannot_read_or_configure_credentials(workspace):
    app, client = workspace
    app.state.db.execute('INSERT INTO users VALUES(?,?,?,?)',(uid(),'reviewer',hash_password('reviewer-test-password'),'reviewer'))
    with TestClient(app) as reviewer:
        assert reviewer.post('/api/auth/login',json={'username':'reviewer','password':'reviewer-test-password'}).status_code == 200
        assert reviewer.get('/api/cases').status_code == 200
        assert reviewer.get('/api/connections').status_code == 403
        assert reviewer.post('/api/tokens',json={'name':'forbidden'}).status_code == 403
        assert reviewer.put('/api/policy',json={'admin_threshold':3,'senior_threshold':4}).status_code == 403

def test_tokens_are_scoped_hashed_and_revocable(workspace, event):
    app, client = workspace
    issued = client.post('/api/tokens', json={'name':'partner'}).json()
    assert issued['token'] not in json.dumps(app.state.db.all('SELECT * FROM tokens'))
    with TestClient(app) as feed:
        headers = {'Authorization':'Bearer '+issued['token']}
        assert feed.get('/api/cases',headers=headers).status_code == 401
        assert feed.post('/api/content-events',json=event,headers=headers).status_code == 202
        client.delete('/api/tokens/'+issued['id'])
        assert feed.post('/api/content-events',json=event,headers=headers).status_code == 401

def test_idempotency_revisions_and_unverified_browser_author(workspace, event):
    app, client = workspace
    first = client.post('/api/content-events',json=event)
    assert first.status_code == 202
    case_id = first.json()['case_id']
    assert client.post('/api/content-events',json=event).json()['duplicate']
    assert client.post('/api/content-events',json={**event,'text':'Different claim'}).status_code == 409
    assert client.post('/api/content-events',json={**event,'event_id':'second'}).status_code == 409
    assert not client.get('/api/cases/'+case_id).json()['author_verified']
    update = {**event,'event_id':'second','revision':2,'event_type':'edited','text':'Apollo 11 landed in 1969.'}
    assert client.post('/api/content-events',json=update).status_code == 202
    assert client.get('/api/cases/'+case_id).json()['status'] == 'superseded'
    assert client.post('/api/cases/'+case_id+'/decisions',json={'decision':'confirmed','reason':'This is no longer current.'}).status_code == 409

def test_private_text_never_confirmable_from_manual_input(workspace, event):
    app, client = workspace
    case_id = client.post('/api/content-events',json=event).json()['case_id']
    assessed(app, case_id)
    assert not client.get('/api/cases/'+case_id).json()['can_confirm']
    assert client.post('/api/cases/'+case_id+'/decisions',json={'decision':'confirmed','reason':'Evidence has been reviewed.','policy_rule':'misinformation','incident_key':'moon'}).status_code == 422

def test_distinct_incidents_escalations_appeal_and_expiry(workspace, event):
    app, client = workspace
    identifiers=[]
    for number, incident in enumerate(['same-event','same-event','second-event','third-event']):
        identifier = ingest(client,{**event,'event_id':f'event-{number}','content_id':f'post-{number}'})
        identifiers.append(identifier)
        assessed(app,identifier)
        assert client.get('/api/cases/'+identifier).json()['can_confirm']
        response = client.post('/api/cases/'+identifier+'/decisions',json={'decision':'confirmed','reason':'Reviewer verified the source and attribution.','policy_rule':'customer-rule-1','incident_key':incident})
        assert response.status_code == 200
    state=response.json()['account']
    assert state['eligible_incidents'] == 3 and state['escalation'] == 'senior_review'
    assert not state['automatic_account_disabling'] and response.json()['external_action'] is None
    appeal=client.post('/api/cases/'+identifiers[-1]+'/decisions',json={'decision':'appealed','reason':'The account holder disputed the context.'})
    assert appeal.json()['account']['eligible_incidents'] == 2
    assert appeal.json()['account']['escalation'] == 'admin_review'
    assert client.post('/api/cases/'+identifiers[-1]+'/decisions',json={'decision':'dismissed','reason':'Invalid state transition.'}).status_code == 409
    client.post('/api/cases/'+identifiers[-1]+'/decisions',json={'decision':'overturned','reason':'The appeal established missing context.'})
    old=(datetime.now(timezone.utc)-timedelta(days=200)).isoformat()
    app.state.db.execute('UPDATE cases SET created=? WHERE id=?',(old,identifiers[-2]))
    assert account_state(app.state.db,'x',event['author_ref'])['eligible_incidents'] == 1

def test_delete_purges_content_sources_agent_outputs_reviews(workspace, event):
    app, client = workspace
    identifier=ingest(client,event)
    assessed(app,identifier)
    app.state.db.execute('INSERT INTO runs(id,case_id,role,status,output,created) VALUES(?,?,?,?,?,?)',(uid(),identifier,'analyst','complete','sensitive output',now()))
    app.state.db.audit('reviewer','review.confirmed',identifier,{'reason':'sensitive text'})
    deletion={**event,'event_id':'delete-1','revision':2,'event_type':'deleted','text':'even delete payload text is purged'}
    tombstone=ingest(client,deletion)
    for case_id in (identifier,tombstone):
        detail=client.get('/api/cases/'+case_id).json()
        assert detail['status']=='deleted' and detail['input']['text']=='' and detail['result'] is None
        assert detail['runs']==[] and detail['author_ref']=='' and detail['review'] is None
    assert 'sensitive' not in dumps(app.state.db.all('SELECT * FROM audit WHERE subject=?',(identifier,)))

def test_connections_encrypt_secrets_and_constrain_network(workspace):
    app, client = workspace
    value={'name':'local','kind':'openai_chat','base_url':'http://127.0.0.1:8087/v1','model':'local','api_key':'secret-unit-test','local_endpoint':True}
    response=client.post('/api/connections',json=value)
    assert response.status_code == 200
    assert 'secret-unit-test' not in dumps(app.state.db.all('SELECT * FROM connections'))
    assert 'secret-unit-test' not in client.get('/api/connections').text
    assert 'secret-unit-test' not in client.get('/api/dashboard').text
    assert app.state.vault.decrypt(app.state.db.one('SELECT secret FROM connections')['secret'])=='secret-unit-test'
    assert client.post('/api/connections',json={**value,'local_endpoint':False}).status_code == 422
    assert client.post('/api/connections',json={**value,'base_url':'http://10.0.0.1/v1'}).status_code == 422
    assert client.delete('/api/connections/'+response.json()['id']).status_code == 409

def test_unconfigured_case_is_blocked_and_retryable(workspace,event):
    import asyncio
    app,client=workspace
    identifier=ingest(client,event)
    case=app.state.db.claim_job()
    asyncio.run(app.state.pipeline.process(case))
    detail=client.get('/api/cases/'+identifier).json()
    assert detail['status']=='blocked' and 'extractor' in detail['error']
    assert client.post('/api/cases/'+identifier+'/retry').status_code==200
    assert client.get('/api/cases/'+identifier).json()['status']=='queued'

def test_restart_recovers_only_active_jobs(workspace,event):
    app,client=workspace
    identifier=ingest(client,event)
    assert app.state.db.claim_job()['id']==identifier
    app.state.db.recover()
    assert app.state.db.one('SELECT status FROM cases WHERE id=?',(identifier,))['status']=='queued'

def test_invalid_policy_and_missing_content(workspace,event):
    _,client=workspace
    assert client.put('/api/policy',json={'admin_threshold':4,'senior_threshold':3}).status_code==422
    assert client.post('/api/content-events',json={**event,'text':''}).status_code==422
    assert client.post('/api/content-events',json={**event,'evidence_urls':['file:///secrets']}).status_code==422
