import base64
import hashlib
import json
import time
from urllib.parse import urlsplit,parse_qs
import pytest
from fastapi.testclient import TestClient
from verifier.db import dumps,uid
from verifier.models import MonitorInput
from verifier.security import hash_password

def configured(client,provider='x'):
    r=client.put('/api/social/apps/'+provider,json={'client_id':'customer-app','client_secret':'customer-secret','graph_version':'' if provider=='x' else 'v23.0'})
    assert r.status_code==200,r.text

def connected(workspace,monkeypatch,provider='x'):
    app,client=workspace
    configured(client,provider)
    calls=[]
    async def call(method,url,**kwargs):
        calls.append((method,url,kwargs))
        if '/oauth' in url and ('access_token' in url or '/token' in url):
            return {'access_token':'personal-access-secret','refresh_token':'personal-refresh-secret','scope':'tweet.read users.read offline.access','expires_in':7200}
        if '/permissions' in url:return {'data':[{'permission':'user_posts','status':'granted'}]}
        if provider=='x':return {'data':{'id':'42','username':'sample-user'}}
        if provider=='facebook':return {'id':'42','name':'Sample person'}
        return {'user_id':'42','username':'sample-creator'}
    monkeypatch.setattr(app.state.social,'call',call)
    start=client.post('/api/social/connect/'+provider)
    assert start.status_code==200,start.text
    params=parse_qs(urlsplit(start.json()['authorization_url']).query)
    callback=client.get('/api/social/callback/'+provider,params={'state':params['state'][0],'code':'single-use-code'},follow_redirects=False)
    assert callback.status_code==303 and callback.headers['location']=='/#demo?notice=connected'
    account=client.get('/api/demo').json()['accounts'][0]
    return account,params,calls

@pytest.mark.parametrize('provider',['x','facebook','instagram'])
def test_customer_oauth_links_account_without_exposing_tokens(workspace,monkeypatch,provider):
    app,client=workspace
    account,params,calls=connected(workspace,monkeypatch,provider)
    assert account['provider']==provider and account['remote_id']=='42'
    assert 'personal-access-secret' not in client.get('/api/demo').text
    assert 'customer-secret' not in client.get('/api/social/apps').text
    stored=app.state.db.one('SELECT * FROM social_accounts WHERE id=?',(account['id'],))
    assert 'personal-access-secret' not in stored['secret']
    assert json.loads(app.state.vault.decrypt(stored['secret']))['access_token']=='personal-access-secret'
    if provider=='x':
        assert params['code_challenge_method']==['S256']
        token_call=calls[0]
        verifier=token_call[2]['form']['code_verifier']
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        assert challenge==params['code_challenge'][0]
        assert token_call[2]['headers']['Authorization'].startswith('Basic ')
        assert 'tweet.write' not in params['scope'][0]
    before=len(calls)
    repeat=client.get('/api/social/callback/'+provider,params={'state':params['state'][0],'code':'single-use-code'},follow_redirects=False)
    assert 'connection_failed' in repeat.headers['location'] and len(calls)==before

def test_oauth_rejects_another_browser_and_survives_strict_cookie_omission(workspace,monkeypatch):
    app,client=workspace
    configured(client)
    state=parse_qs(urlsplit(client.post('/api/social/connect/x').json()['authorization_url']).query)['state'][0]
    with TestClient(app) as other:
        response=other.get('/api/social/callback/x',params={'state':state,'code':'stolen'},follow_redirects=False)
        assert 'connection_failed' in response.headers['location']
    assert app.state.db.one('SELECT digest FROM oauth_states')
    async def exchange(*args):return {'access_token':'secret','scope':'tweet.read users.read','expires_in':7200}
    async def identity(*args):return '42','Person'
    monkeypatch.setattr(app.state.social,'exchange',exchange)
    monkeypatch.setattr(app.state.social,'identity',identity)
    client.cookies.delete('cv_session')  # Cross-site callback sends only the Lax binding cookie.
    response=client.get('/api/social/callback/x',params={'state':state,'code':'valid'},follow_redirects=False)
    assert response.headers['location']=='/#demo?notice=connected'

def test_logout_invalidates_pending_oauth(workspace):
    app,client=workspace;configured(client)
    state=parse_qs(urlsplit(client.post('/api/social/connect/x').json()['authorization_url']).query)['state'][0]
    client.post('/api/auth/logout')
    r=client.get('/api/social/callback/x',params={'state':state,'code':'unused'},follow_redirects=False)
    assert 'connection_failed' in r.headers['location'] and not app.state.db.all('SELECT * FROM social_accounts')

def test_personal_demo_is_private_and_never_counts_for_enforcement(workspace):
    app,client=workspace
    body={'platform':'facebook','text':'A post for a personal-account demonstration.','source_url':'https://www.facebook.com/person/posts/123'}
    first=client.post('/api/demo/investigate',json=body)
    assert first.status_code==202
    identifier=first.json()['case_id']
    assert client.post('/api/demo/investigate',json=body).json()['duplicate']
    case=client.get('/api/cases/'+identifier).json()
    assert case['is_demo'] and not case['author_verified'] and not case['can_confirm']
    app.state.db.execute('INSERT INTO users VALUES(?,?,?,?)',(uid(),'reviewer',hash_password('private-demo-test-password'),'reviewer'))
    with TestClient(app) as reviewer:
        reviewer.post('/api/auth/login',json={'username':'reviewer','password':'private-demo-test-password'})
        assert reviewer.get('/api/cases/'+identifier).status_code==404
        assert reviewer.get('/api/cases/'+identifier+'/export').status_code==404
        assert not reviewer.get('/api/cases').json()
        assert reviewer.post('/api/cases/'+identifier+'/retry').status_code==404
        assert reviewer.delete('/api/demo/cases/'+identifier).status_code==404
    assert client.post('/api/content-events',json={'event_id':'guess','content_id':case['content_id'],'platform':'facebook','revision':2,'event_type':'deleted'}).status_code==403

def test_demo_quota_and_deletion_when_platform_disabled(workspace):
    app,client=workspace
    client.put('/api/workspace',json={'demo_daily_limit':1})
    first=client.post('/api/demo/investigate',json={'platform':'instagram','text':'First caption'}).json()['case_id']
    assert client.post('/api/demo/investigate',json={'text':'Second claim'}).status_code==429
    client.put('/api/platforms/instagram',json={'display_name':'Instagram','enabled':False})
    assert client.delete('/api/demo/cases/'+first).status_code==200
    assert client.get('/api/demo').json()['used_today']==1
    assert client.get('/api/cases/'+first).json()['input']['text']==''

@pytest.mark.parametrize('provider,post',[('x',{'id':'100','text':'A short post','note_tweet':{'text':'The full post for checking'},'created_at':'2026-09-06T01:00:00Z'}),('facebook',{'id':'42_100','message':'The full post for checking','permalink_url':'https://www.facebook.com/42/posts/100','created_time':'2026-09-06T01:00:00+0000'}),('instagram',{'id':'100','caption':'The full post for checking','permalink':'https://www.instagram.com/p/sample/','timestamp':'2026-09-06T01:00:00Z'})])
def test_recent_posts_can_be_selected_and_investigated(workspace,monkeypatch,provider,post):
    app,client=workspace
    account,_,_=connected(workspace,monkeypatch,provider)
    async def posts(*args,**kwargs):return {'data':[post]}
    monkeypatch.setattr(app.state.social,'call',posts)
    response=client.post('/api/social/accounts/'+account['id']+'/posts',json={})
    assert response.status_code==200,response.text
    candidate=response.json()['posts'][0]
    assert candidate['text']=='The full post for checking'
    result=client.post('/api/demo/investigate',json={'post_id':candidate['id']})
    assert result.status_code==202,result.text
    detail=client.get('/api/cases/'+result.json()['case_id']).json()
    assert detail['is_demo'] and detail['platform']==provider and detail['input']['posted_at']
    client.delete('/api/social/accounts/'+account['id'])
    assert not app.state.db.all('SELECT * FROM social_posts')
    assert client.post('/api/demo/investigate',json={'post_id':candidate['id']}).status_code==404

@pytest.mark.asyncio
async def test_opt_in_monitor_persists_and_deduplicates(workspace,monkeypatch):
    app,client=workspace
    account,_,_=connected(workspace,monkeypatch)
    async def posts(*args,**kwargs):return {'data':[{'id':'100','text':'A monitored post'}]}
    monkeypatch.setattr(app.state.social,'call',posts)
    row=app.state.social.account(account['id'],app.state.db.one('SELECT id FROM users')['id'])
    await app.state.social.poll_account(row)
    assert not app.state.db.all('SELECT * FROM cases')
    assert client.put('/api/social/accounts/'+account['id']+'/monitor',json={'enabled':True,'interval_minutes':5}).status_code==200
    row=app.state.social.account(account['id'],row['owner_id'])
    await app.state.social.poll_account(row);await app.state.social.poll_account(row)
    assert len(app.state.db.all('SELECT * FROM cases'))==1
    assert json.loads(row['monitor'])['enabled']

@pytest.mark.asyncio
async def test_x_refresh_and_disconnect_race(workspace,monkeypatch):
    app,client=workspace
    account,_,_=connected(workspace,monkeypatch)
    row=app.state.db.one('SELECT * FROM social_accounts WHERE id=?',(account['id'],))
    row['expires']=0
    async def refresh(method,url,**kwargs):
        assert kwargs['form']['grant_type']=='refresh_token'
        return {'access_token':'renewed-secret','refresh_token':'rotated-secret','expires_in':7200}
    monkeypatch.setattr(app.state.social,'call',refresh)
    assert await app.state.social.token(row)=='renewed-secret'
    async def delayed(method,url,**kwargs):
        app.state.db.execute('DELETE FROM social_accounts WHERE id=?',(row['id'],))
        return {'data':[{'id':'100','text':'A delayed post response'}]}
    monkeypatch.setattr(app.state.social,'call',delayed)
    from verifier.social import SocialError
    with pytest.raises(SocialError,match='disconnected'):await app.state.social.fetch_posts(row['id'],row['owner_id'])
    assert not app.state.db.all('SELECT * FROM social_posts')

def test_expired_binding_and_unconfigured_links_fail_clearly(workspace):
    app,client=workspace
    assert client.post('/api/social/connect/x').status_code==422
    configured(client)
    response=client.post('/api/social/connect/x')
    state=parse_qs(urlsplit(response.json()['authorization_url']).query)['state'][0]
    app.state.db.execute('UPDATE oauth_states SET expires=0')
    r=client.get('/api/social/callback/x',params={'state':state,'code':'unused'},follow_redirects=False)
    assert 'connection_failed' in r.headers['location']


@pytest.mark.asyncio
async def test_disabling_monitor_during_fetch_prevents_new_checks(workspace,monkeypatch):
    app,client=workspace
    account,_,_=connected(workspace,monkeypatch)
    client.put('/api/social/accounts/'+account['id']+'/monitor',json={'enabled':True})
    row=app.state.db.one('SELECT * FROM social_accounts WHERE id=?',(account['id'],))
    async def delayed(*args,**kwargs):
        app.state.db.execute('UPDATE social_accounts SET monitor=? WHERE id=?',(dumps(MonitorInput().model_dump()),row['id']))
        return {'data':[{'id':'100','text':'Late post response'}]}
    monkeypatch.setattr(app.state.social,'call',delayed)
    await app.state.social.poll_account(row)
    assert not app.state.db.all('SELECT * FROM cases')
