"""Customer-owned OAuth apps and read-only connected-account demo workflows."""
import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from pydantic import ValidationError
from urllib.parse import urlencode, urlsplit
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from . import network
from .configuration import profile, workspace_config, PLATFORMS
from .db import dumps, now, uid
from .intake import enqueue
from .models import SocialAppInput, DemoInput, MonitorInput, ContentInput
from .security import digest

SCOPES = {'x':'tweet.read users.read offline.access','facebook':'public_profile,user_posts','instagram':'instagram_business_basic'}
NOTES = {
    'x':'Personal X accounts through OAuth 2.0. A customer developer app and API access are required.',
    'facebook':'Your own posts through Facebook Login and user_posts. Availability depends on the customer app permissions and Meta review.',
    'instagram':'Creator and business accounts through Instagram Login. Personal accounts can use the caption-paste demo; the professional API does not provide a personal-account feed.',
}

class SocialError(Exception):
    pass

def safe_id(value):
    value = str(value)
    if not re.fullmatch(r'[0-9_]{1,100}',value):
        raise SocialError('Platform returned an invalid object identifier')
    return value

def base_url():
    value = os.environ.get('VERIFIER_PUBLIC_URL','http://127.0.0.1:8791').rstrip('/')
    try: parts = network.validate_url(value)
    except network.NetworkError as exc: raise SocialError(str(exc)) from None
    if parts.path or parts.query or parts.fragment or (parts.scheme!='https' and parts.hostname not in ('localhost','127.0.0.1','::1')):
        raise SocialError('Set VERIFIER_PUBLIC_URL to the HTTPS origin of this deployment (loopback HTTP is allowed for development)')
    return value

def canonical_url(value, provider):
    if not value: return ''
    try: parts=network.validate_url(value)
    except network.NetworkError as exc: raise SocialError(str(exc)) from None
    allowed={'x':{'x.com','www.x.com','twitter.com','www.twitter.com'},'facebook':{'facebook.com','www.facebook.com','m.facebook.com'},'instagram':{'instagram.com','www.instagram.com'}}
    if provider in allowed and parts.hostname not in allowed[provider]:
        raise SocialError('Use a post URL from the selected platform')
    if parts.port not in (None,80,443): raise SocialError('Custom post URL ports are not allowed')
    # Facebook story URLs carry their post identity in the query string.
    query='?'+parts.query if provider=='facebook' and parts.path.endswith('story.php') else ''
    return 'https://'+parts.hostname.removeprefix('www.').replace('twitter.com','x.com')+parts.path.rstrip('/')+query

class Social:
    def __init__(self,db,vault):
        self.db,self.vault=db,vault
        self.task=None
        self.locks={}

    def app(self,provider):
        if provider not in SCOPES: raise SocialError('Unsupported social platform')
        value=self.db.setting('social_app:'+provider)
        if not value: raise SocialError('Ask the workspace administrator to configure this platform app first')
        return value

    def callback_url(self,provider):
        return base_url()+'/api/social/callback/'+provider

    def account(self,identifier,owner):
        row=self.db.one('SELECT * FROM social_accounts WHERE id=? AND owner_id=?',(identifier,owner))
        if not row: raise HTTPException(404,'Connected account not found')
        return row

    def public_account(self,row):
        return {key:value for key,value in row.items() if key not in ('secret','owner_id')} | {'monitor':json.loads(row['monitor'])}

    async def call(self,method,url,**kwargs):
        try:
            status,_,raw=await network.request(method,url,timeout=30,max_bytes=1_000_000,**kwargs)
        except network.NetworkError as exc:
            raise SocialError(str(exc)) from None
        if not 200<=status<300:
            reason = 'Reconnect the account and check the app permissions.' if status in (400,401,403) else 'Platform rate limit reached. Try again later.' if status==429 else 'The platform service is unavailable.'
            raise SocialError(f'Platform returned HTTP {status}. {reason}')
        try:
            result=json.loads(raw)
            if not isinstance(result,dict) or result.get('error'): raise ValueError()
            return result
        except (ValueError,TypeError): raise SocialError('Platform returned an invalid response') from None

    def x_auth(self,app):
        secret=self.vault.decrypt(app['secret'])
        headers={'Content-Type':'application/x-www-form-urlencoded'}
        if secret:
            headers['Authorization']='Basic '+base64.b64encode((app['client_id']+':'+secret).encode()).decode()
        return headers

    async def exchange(self,provider,code,verifier,app):
        redirect=self.callback_url(provider)
        if provider=='x':
            result=await self.call('POST','https://api.x.com/2/oauth2/token',form={'grant_type':'authorization_code','code':code,'client_id':app['client_id'],'redirect_uri':redirect,'code_verifier':verifier},headers=self.x_auth(app))
        elif provider=='facebook':
            query=urlencode({'client_id':app['client_id'],'client_secret':self.vault.decrypt(app['secret']),'redirect_uri':redirect,'code':code})
            result=await self.call('GET','https://graph.facebook.com/'+app['graph_version']+'/oauth/access_token?'+query)
        else:
            result=await self.call('POST','https://api.instagram.com/oauth/access_token',form={'client_id':app['client_id'],'client_secret':self.vault.decrypt(app['secret']),'grant_type':'authorization_code','redirect_uri':redirect,'code':code})
            if 'access_token' not in result and isinstance(result.get('data'),list) and result['data']:
                result=result['data'][0]
        if not isinstance(result.get('access_token'),str) or not result['access_token']:
            raise SocialError('Platform did not return an access token')
        return result

    def graph_params(self,provider,app,token,**params):
        if provider=='facebook':
            params['appsecret_proof']=hmac.new(self.vault.decrypt(app['secret']).encode(),token.encode(),hashlib.sha256).hexdigest()
        return urlencode(params)

    async def identity(self,provider,token,app):
        headers={'Authorization':'Bearer '+token}
        if provider=='x':
            result=await self.call('GET','https://api.x.com/2/users/me?user.fields=username',headers=headers)
            user=result.get('data',{})
            return safe_id(user.get('id','')),str(user.get('username') or user.get('name') or user['id'])[:120]
        if provider=='facebook':
            prefix='https://graph.facebook.com/'+app['graph_version']
            user=await self.call('GET',prefix+'/me?'+self.graph_params(provider,app,token,fields='id,name'),headers=headers)
            permissions=await self.call('GET',prefix+'/me/permissions?'+self.graph_params(provider,app,token),headers=headers)
            if not any(p.get('permission')=='user_posts' and p.get('status')=='granted' for p in permissions.get('data',[])):
                raise SocialError('Facebook user_posts permission was not granted. The caption-paste demo remains available.')
            return safe_id(user.get('id','')),str(user.get('name',user['id']))[:120]
        user=await self.call('GET','https://graph.instagram.com/'+app['graph_version']+'/me?fields=user_id,username',headers=headers)
        return safe_id(user.get('user_id') or user.get('id','')),str(user.get('username','Instagram account'))[:120]

    async def token(self,row):
        if row['status']!='active' or not row['secret']:
            raise SocialError('Reconnect this account before fetching posts')
        values=json.loads(self.vault.decrypt(row['secret']))
        if row['expires']>time.time()+90: return values['access_token']
        if row['provider']=='x' and values.get('refresh_token'):
            app=self.app('x')
            updated=await self.call('POST','https://api.x.com/2/oauth2/token',form={'grant_type':'refresh_token','refresh_token':values['refresh_token'],'client_id':app['client_id']},headers=self.x_auth(app))
            if not updated.get('access_token'): raise SocialError('Token refresh failed; reconnect the account')
            values.update(updated)
            written=self.db.execute("UPDATE social_accounts SET secret=?,expires=?,status='active',error=NULL WHERE id=? AND secret=? AND status='active'",(self.vault.encrypt(dumps(values)),time.time()+int(updated.get('expires_in',7200)),row['id'],row['secret']))
            if not written: raise SocialError('Account was disconnected or its credentials changed')
            return values['access_token']
        self.db.execute("UPDATE social_accounts SET status='expired',error='Access expired; reconnect the account' WHERE id=?",(row['id'],))
        raise SocialError('Access expired. Reconnect the account to fetch posts. Monitoring remains paused until then.')

    async def fetch_posts(self,identifier,owner,lookup_url=''):
        async with self.locks.setdefault(identifier,asyncio.Lock()):
            row=self.account(identifier,owner)
            provider=row['provider']; app=self.app(provider)
            if not profile(self.db,provider)['enabled']: raise SocialError('This platform is disabled')
            token=await self.token(row);headers={'Authorization':'Bearer '+token}
            credential=self.db.one("SELECT secret FROM social_accounts WHERE id=? AND status='active'",(identifier,))
            if not credential or not credential['secret']: raise SocialError('Account was disconnected or its credentials changed')
            if provider=='x':
                fields='id,text,author_id,created_at,lang,edit_history_tweet_ids,note_tweet'
                if lookup_url:
                    url=canonical_url(lookup_url,provider)
                    match=re.search(r'/status/(\d+)(?:/|$)',urlsplit(url).path)
                    if not match: raise SocialError('Use an X post URL containing /status/ and its post ID')
                    result=await self.call('GET','https://api.x.com/2/tweets/'+match[1]+'?'+urlencode({'tweet.fields':fields}),headers=headers)
                    posts=[result.get('data',{})]
                else:
                    result=await self.call('GET','https://api.x.com/2/users/'+safe_id(row['remote_id'])+'/tweets?'+urlencode({'tweet.fields':fields,'max_results':10,'exclude':'retweets,replies'}),headers=headers)
                    posts=result.get('data',[])
            else:
                host='graph.facebook.com' if provider=='facebook' else 'graph.instagram.com'
                suffix='posts' if provider=='facebook' else 'media'
                fields='id,message,created_time,permalink_url' if provider=='facebook' else 'id,caption,media_type,permalink,timestamp'
                result=await self.call('GET',f'https://{host}/{app["graph_version"]}/{safe_id(row["remote_id"])}/{suffix}?'+self.graph_params(provider,app,token,fields=fields,limit=10),headers=headers)
                posts=result.get('data',[])
            if not isinstance(posts,list): raise SocialError('Platform post list was malformed')
            returned=[]
            with self.db.connect() as tx:
                # Disconnect wins over a late provider response.
                if not tx.execute("SELECT id FROM social_accounts WHERE id=? AND secret=? AND status='active'",(identifier,credential['secret'])).fetchone(): raise SocialError('Account was disconnected or its credentials changed')
                for post in posts[:10]:
                    if not isinstance(post,dict): raise SocialError('Platform returned a malformed post')
                    remote=safe_id(post.get('id',''))
                    if provider=='x':
                        text=(post.get('note_tweet') or {}).get('text') or post.get('text','')
                        history=post.get('edit_history_tweet_ids') or [remote]
                        stable=safe_id(history[0]);url='https://x.com/i/status/'+remote
                    else:
                        text=post.get('message' if provider=='facebook' else 'caption','')
                        stable=remote;url=post.get('permalink_url' if provider=='facebook' else 'permalink','')
                    if not isinstance(text,str) or not text.strip(): continue
                    if len(text)>16000: raise SocialError('A post exceeds the text budget. Supply a complete, shorter claim excerpt instead.')
                    url=canonical_url(url,provider)
                    if lookup_url and provider!='x' and canonical_url(lookup_url,provider)!=url: continue
                    key=digest(identifier+':'+stable)
                    posted=post.get('created_at') or post.get('created_time') or post.get('timestamp')
                    tx.execute('INSERT INTO social_posts VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET text=excluded.text,source_url=excluded.source_url,posted_at=excluded.posted_at,seen_at=excluded.seen_at',(key,identifier,stable,text,url,posted,now()))
                    returned.append(key)
                tx.execute("UPDATE social_accounts SET last_sync=?,error=NULL,status='active' WHERE id=?",(now(),identifier))
            if lookup_url and not returned: raise SocialError('This post was not returned by the connected account API. Paste its text or caption to investigate it.')
            return [self.db.one('SELECT * FROM social_posts WHERE id=?',(key,)) for key in returned]

    def submit(self,body,actor):
        if body.post_id:
            post=self.db.one('SELECT p.*,a.provider,a.owner_id FROM social_posts p JOIN social_accounts a ON a.id=p.account_id WHERE p.id=? AND a.owner_id=?',(body.post_id,actor['id']))
            if not post: raise HTTPException(404,'Post not found in your connected accounts')
            platform,text,url,posted=post['provider'],post['text'],post['source_url'],post['posted_at']
            key='post:'+post['id']
        else:
            platform,text=body.platform,body.text
            url=canonical_url(body.source_url,platform) if body.source_url else ''
            posted=None;key=url or digest(text)
        if not text.strip(): raise HTTPException(422,'Paste the post text or select a retrieved post. A URL alone is not treated as evidence.')
        content_id='demo:'+actor['id']+':'+digest(key)
        latest=self.db.one('SELECT * FROM cases WHERE platform=? AND content_id=? ORDER BY revision DESC LIMIT 1',(platform,content_id))
        revision=latest['revision']+1 if latest else 1
        try:
            content=ContentInput(event_id='demo:'+uid(),platform=platform,content_id=content_id,revision=revision,event_type='edited' if latest else 'created',text=text,source_url=url,evidence_urls=body.evidence_urls,allow_external_processing=body.allow_external_processing,allow_web_search=body.allow_web_search,posted_at=posted)
        except ValidationError:
            raise HTTPException(422,'Check the post date and evidence URLs; only valid public HTTP(S) evidence URLs are accepted') from None
        if latest and latest['status']!='deleted':
            previous=json.loads(latest['input'])
            compared=('text','source_url','evidence_urls','allow_external_processing','allow_web_search')
            if all(previous.get(k)==content.model_dump().get(k) for k in compared):
                return {'case_id':latest['id'],'duplicate':True}
        return enqueue(self.db,content,actor,demo_owner=actor['id'])

    async def poll_account(self,row):
        monitor=MonitorInput.model_validate_json(row['monitor'])
        if not monitor.enabled: return
        actor=self.db.one('SELECT id,username,role FROM users WHERE id=?',(row['owner_id'],))
        if not actor: return
        try:
            posts=await self.fetch_posts(row['id'],row['owner_id'])
            current=self.db.one('SELECT monitor FROM social_accounts WHERE id=?',(row['id'],))
            if not current: return
            monitor=MonitorInput.model_validate_json(current['monitor'])
            if not monitor.enabled: return
            for post in posts[:monitor.batch_limit]:
                self.submit(DemoInput(post_id=post['id'],allow_external_processing=monitor.allow_external_processing,allow_web_search=monitor.allow_web_search),actor)
        except (SocialError,HTTPException) as exc:
            message=str(exc) if isinstance(exc,SocialError) else str(exc.detail)
            self.db.execute('UPDATE social_accounts SET error=? WHERE id=?',(message,row['id']))
        except Exception:
            self.db.execute("UPDATE social_accounts SET error='Poll failed; inspect the connection and retry' WHERE id=?",(row['id'],))

    async def worker(self):
        while True:
            self.db.execute('DELETE FROM oauth_states WHERE expires<?',(time.time(),))
            self.db.execute('DELETE FROM social_posts WHERE seen_at<?',((datetime.now(timezone.utc)-timedelta(hours=24)).isoformat(),))
            for row in self.db.all("SELECT * FROM social_accounts WHERE next_poll<=? AND status='active' ORDER BY next_poll LIMIT 10",(time.time(),)):
                monitor=json.loads(row['monitor'])
                interval=max(300,int(monitor.get('interval_minutes',15))*60)
                self.db.execute('UPDATE social_accounts SET next_poll=? WHERE id=?',(time.time()+interval,row['id']))
                if monitor.get('enabled'): await self.poll_account(row)
            await asyncio.sleep(5)

    def start(self): self.task=asyncio.create_task(self.worker())
    async def stop(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task,return_exceptions=True)

def social_router(service,user,admin):
    router=APIRouter()
    db,vault=service.db,service.vault

    @router.get('/api/social/apps')
    async def apps(actor=Depends(admin)):
        result=[]
        for provider in SCOPES:
            value=db.setting('social_app:'+provider,{})
            result.append({'provider':provider,'configured':bool(value),'client_id':value.get('client_id',''),'graph_version':value.get('graph_version',''),'credential_configured':bool(value.get('secret')),'callback_url':service.callback_url(provider),'scopes':SCOPES[provider],'note':NOTES[provider]})
        return result

    @router.put('/api/social/apps/{provider}')
    async def app_save(provider:str,body:SocialAppInput,actor=Depends(admin)):
        if provider not in SCOPES: raise HTTPException(404,'Unsupported platform')
        existing=db.setting('social_app:'+provider,{})
        secret=vault.encrypt(body.client_secret) if body.client_secret else existing.get('secret','')
        if provider!='x' and (not secret or not body.graph_version): raise HTTPException(422,'Meta connections require an app secret and Graph API version from your developer app')
        revision=uid()
        with db.connect() as tx:
            value={'client_id':body.client_id,'secret':secret,'graph_version':body.graph_version,'revision':revision}
            tx.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('social_app:'+provider,dumps(value)))
            tx.execute('DELETE FROM oauth_states WHERE provider=?',(provider,))
            if existing and (existing.get('client_id')!=body.client_id or body.client_secret):
                tx.execute("UPDATE social_accounts SET status='expired',secret='',error='App credentials changed; reconnect' WHERE provider=?",(provider,))
        db.audit(actor['username'],'social_app.configured',provider,{'client_id':body.client_id,'graph_version':body.graph_version})
        return {'ok':True}

    @router.get('/api/demo')
    async def demo(actor=Depends(user)):
        accounts=[service.public_account(row) for row in db.all('SELECT * FROM social_accounts WHERE owner_id=? ORDER BY provider,display_name',(actor['id'],))]
        cases=db.all('SELECT id,platform,status,input,created FROM cases WHERE is_demo=1 AND owner_id=? ORDER BY created DESC LIMIT 20',(actor['id'],))
        for row in cases: row['text']=json.loads(row.pop('input'))['text'][:240]
        used=db.one("SELECT COUNT(*) AS n FROM cases WHERE is_demo=1 AND owner_id=? AND created>=? AND json_extract(input,'$.event_type')!='deleted'",(actor['id'],now()[:10]))['n']
        return {'accounts':accounts,'cases':cases,'daily_limit':workspace_config(db)['demo_daily_limit'],'used_today':used,
            'connection_notice':db.setting('social_notice:'+actor['id'],''),
            'platforms':[{'provider':provider,'configured':bool(db.setting('social_app:'+provider)),'enabled':profile(db,provider)['enabled'],'note':NOTES[provider]} for provider in SCOPES]}

    @router.post('/api/social/connect/{provider}')
    async def connect(provider:str,request:Request,response:Response,actor=Depends(user)):
        app=service.app(provider)
        if not profile(db,provider)['enabled']: raise HTTPException(403,'Platform disabled')
        state,binding,verifier=secrets.token_urlsafe(32),secrets.token_urlsafe(32),secrets.token_urlsafe(48)
        session_digest=digest(request.cookies.get('cv_session',''))
        db.execute('DELETE FROM oauth_states WHERE owner_id=?',(actor['id'],))
        db.execute('INSERT INTO oauth_states VALUES(?,?,?,?,?,?,?,?)',(digest(state),provider,actor['id'],session_digest,digest(binding),vault.encrypt(verifier),app['revision'],time.time()+600))
        params={'response_type':'code','client_id':app['client_id'],'redirect_uri':service.callback_url(provider),'scope':SCOPES[provider],'state':state}
        if provider=='x':
            params.update(code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='),code_challenge_method='S256')
            endpoint='https://x.com/i/oauth2/authorize'
        elif provider=='facebook': endpoint='https://www.facebook.com/'+app['graph_version']+'/dialog/oauth'
        else: endpoint='https://www.instagram.com/oauth/authorize'
        response.set_cookie('cv_oauth_binding',binding,httponly=True,samesite='lax',secure=base_url().startswith('https:'),max_age=600,path='/api/social/callback')
        return {'authorization_url':endpoint+'?'+urlencode(params)}

    @router.get('/api/social/callback/{provider}')
    async def callback(provider:str,request:Request):
        params=dict(request.query_params)
        # Uvicorn logs response start; discard codes/state from the log scope.
        request.scope['query_string']=b''
        response=RedirectResponse('/#demo?notice=connected',status_code=303)
        response.delete_cookie('cv_oauth_binding',path='/api/social/callback')
        state=None
        try:
            with db.connect() as tx:
                tx.execute('BEGIN IMMEDIATE')
                record=tx.execute('SELECT * FROM oauth_states WHERE digest=?',(digest(params.get('state','')),)).fetchone()
                if not record: raise SocialError('Authorization state is invalid or already used')
                state=dict(record)
                if state['provider']!=provider or state['expires']<=time.time() or not hmac.compare_digest(state['binding_digest'],digest(request.cookies.get('cv_oauth_binding',''))): raise SocialError('Authorization session mismatch or timeout')
                if not tx.execute('SELECT digest FROM sessions WHERE digest=? AND user_id=? AND expires>?',(state['session_digest'],state['owner_id'],time.time())).fetchone(): raise SocialError('Workspace session ended; sign in and reconnect')
                tx.execute('DELETE FROM oauth_states WHERE digest=?',(state['digest'],))
            if params.get('error') or not params.get('code'): raise SocialError('Authorization was declined or did not return a code')
            app=service.app(provider)
            if state['app_revision']!=app['revision']: raise SocialError('App settings changed during authorization')
            tokens=await service.exchange(provider,params['code'],vault.decrypt(state['verifier']),app)
            remote,name=await service.identity(provider,tokens['access_token'],app)
            if provider=='x' and not {'tweet.read','users.read'}<=set(tokens.get('scope','').split()): raise SocialError('X did not grant the required read permissions')
            expires=time.time()+min(int(tokens.get('expires_in',3600)),60*86400)
            with db.connect() as tx:
                # Logout or an app rotation while the provider was responding wins.
                if not tx.execute('SELECT digest FROM sessions WHERE digest=? AND expires>?',(state['session_digest'],time.time())).fetchone(): raise SocialError('Workspace session ended')
                current=json.loads(tx.execute('SELECT value FROM settings WHERE key=?',('social_app:'+provider,)).fetchone()['value'])
                if current['revision']!=state['app_revision']: raise SocialError('App settings changed')
                tx.execute("INSERT INTO social_accounts(id,owner_id,provider,remote_id,display_name,secret,expires,scopes,status,monitor,next_poll) VALUES(?,?,?,?,?,?,?,?,'active',?,?) ON CONFLICT(owner_id,provider,remote_id) DO UPDATE SET display_name=excluded.display_name,secret=excluded.secret,expires=excluded.expires,scopes=excluded.scopes,status='active',error=NULL",(uid(),state['owner_id'],provider,remote,name,vault.encrypt(dumps(tokens)),expires,tokens.get('scope',SCOPES[provider]),dumps(MonitorInput().model_dump()),time.time()+900))
            db.set_setting('social_notice:'+state['owner_id'],'')
            db.audit(state['owner_id'],'social.connected',provider,{'remote_id':remote})
        except (SocialError,ValueError,KeyError) as exc:
            response.headers['location']='/#demo?notice=connection_failed'
            if state:
                db.set_setting('social_notice:'+state['owner_id'],str(exc) if isinstance(exc,SocialError) else 'The platform response could not be verified. Check app permissions and reconnect.')
        return response

    @router.post('/api/social/accounts/{identifier}/posts')
    async def fetch(identifier:str,body:DemoInput,actor=Depends(user)):
        posts=await service.fetch_posts(identifier,actor['id'],body.source_url)
        return {'posts':posts,'note':'Only returned text/captions are analyzed; image, audio and video contents are not inspected.'}

    @router.put('/api/social/accounts/{identifier}/monitor')
    async def monitor(identifier:str,body:MonitorInput,actor=Depends(user)):
        row=service.account(identifier,actor['id']);config=profile(db,row['provider'])
        if body.enabled and (row['status']!='active' or not config['enabled']): raise HTTPException(409,'Reconnect and enable the platform before monitoring')
        if body.enabled and ((body.allow_external_processing and not config['allow_hosted']) or (body.allow_web_search and not config['allow_search'])): raise HTTPException(403,'Platform policy disallows this processing option')
        db.execute('UPDATE social_accounts SET monitor=?,next_poll=? WHERE id=?',(dumps(body.model_dump()),time.time() if body.enabled else time.time()+86400,identifier))
        db.audit(actor['username'],'social.monitor_updated',identifier,body.model_dump())
        return {'ok':True}

    @router.delete('/api/social/accounts/{identifier}')
    async def disconnect(identifier:str,actor=Depends(user)):
        service.account(identifier,actor['id'])
        db.execute('DELETE FROM social_accounts WHERE id=?',(identifier,))
        db.audit(actor['username'],'social.disconnected',identifier)
        return {'ok':True,'note':'Local credentials and cached posts removed. You can also revoke the app in the platform account settings. Existing investigations remain until you delete them.'}

    @router.post('/api/demo/investigate',status_code=202)
    async def investigate(body:DemoInput,actor=Depends(user)):
        return service.submit(body,actor)

    @router.delete('/api/demo/cases/{identifier}')
    async def delete_case(identifier:str,actor=Depends(user)):
        row=db.one('SELECT * FROM cases WHERE id=? AND is_demo=1 AND owner_id=?',(identifier,actor['id']))
        if not row: raise HTTPException(404,'Demo case not found')
        latest=db.one('SELECT MAX(revision) AS revision FROM cases WHERE platform=? AND content_id=?',(row['platform'],row['content_id']))
        return enqueue(db,ContentInput(event_id='demo:'+uid(),platform=row['platform'],content_id=row['content_id'],revision=latest['revision']+1,event_type='deleted'),actor,demo_owner=actor['id'])

    return router
