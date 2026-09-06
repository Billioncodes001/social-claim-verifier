import asyncio
import hashlib
import json
import os
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .db import Database, now, uid, dumps
from .security import Vault, hash_password, verify_password, digest
from .models import Credentials, ConnectionInput, RoleInput, ContentInput, DecisionInput, TokenInput, SearchInput, PolicyInput, ROLES, WorkspaceInput, PlatformProfile
from .intake import enqueue
from .configuration import bootstrap, readiness, workspace_config, profile, PLATFORMS
from .social import Social, SocialError, social_router
from .providers import Providers, ProviderError
from .evidence import Evidence
from .pipeline import Pipeline
from .policy import account_state, can_confirm, DEFAULT
from .network import validate_url, NetworkError, pinned_url

STATIC = Path(__file__).parent / 'static'

def create_app(data_dir=None, run_workers=True):
    root = Path(data_dir or os.environ.get('VERIFIER_DATA_DIR', '.runtime')).resolve()
    db = Database(root)
    bootstrap(db)
    vault = Vault(root)
    providers = Providers(db, vault)
    evidence = Evidence(db, vault)
    pipeline = Pipeline(db, providers, evidence)
    social = Social(db, vault)
    login_attempts = {}

    @asynccontextmanager
    async def lifespan(app):
        if run_workers:
            pipeline.start()
            social.start()
        yield
        await pipeline.stop()
        await social.stop()

    app = FastAPI(title='Claim Verifier', version='0.2.0', lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.db, app.state.vault, app.state.pipeline = db, vault, pipeline
    app.state.social = social
    @app.exception_handler(SocialError)
    async def social_error(request, exc):
        return JSONResponse({'detail':str(exc)}, status_code=422)
    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        # Validation errors must not echo submitted keys, passwords, or content.
        return JSONResponse({'detail': [{'loc': list(item['loc']), 'msg': item['msg'], 'type': item['type']} for item in exc.errors()]}, 422)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=os.environ.get('VERIFIER_ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(','))

    @app.middleware('http')
    async def boundaries(request: Request, call_next):
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            origin = request.headers.get('origin')
            if origin and urlsplit(origin).netloc != request.headers.get('host'):
                return JSONResponse({'detail': 'Cross-origin writes are not permitted'}, 403)
            try:
                if int(request.headers.get('content-length', '0')) > 150000:
                    return JSONResponse({'detail': 'Request too large'}, 413)
            except ValueError:
                return JSONResponse({'detail': 'Invalid content length'}, 400)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 150000:
                    return JSONResponse({'detail': 'Request too large'}, 413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        response.headers['Cache-Control'] = 'no-store' if request.url.path.startswith('/api') else 'no-cache'
        return response

    async def user(request: Request):
        token = request.cookies.get('cv_session', '')
        row = db.one('SELECT u.id,u.username,u.role FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.digest=? AND s.expires>?', (digest(token), time.time())) if token else None
        if not row:
            raise HTTPException(401, 'Sign in to continue')
        return row

    async def admin(actor=Depends(user)):
        if actor['role'] != 'admin':
            raise HTTPException(403, 'Administrator access required')
        return actor

    async def ingest_actor(request: Request):
        bearer = request.headers.get('authorization', '')
        if bearer.startswith('Bearer '):
            token = db.one('SELECT id,name FROM tokens WHERE digest=?', (digest(bearer[7:]),))
            if token:
                return {'username': 'integration:' + token['name'], 'role': 'ingest'}
            raise HTTPException(401, 'Invalid integration token')
        return await user(request)

    def session(response, actor_id):
        token = secrets.token_urlsafe(32)
        db.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
        db.execute('INSERT INTO sessions VALUES(?,?,?)', (digest(token), actor_id, time.time()+43200))
        response.set_cookie('cv_session', token, httponly=True, samesite='strict', secure=os.environ.get('VERIFIER_SECURE_COOKIES') == '1', max_age=43200)

    def find_case(case_id, actor=None):
        row = db.one('SELECT * FROM cases WHERE id=?', (case_id,))
        if not row or (row['is_demo'] and actor and actor['role'] != 'admin' and row['owner_id'] != actor['id']):
            raise HTTPException(404, 'Case not found')
        return row

    def public_connection(row):
        return {key: value for key, value in row.items() if key != 'secret'} | {'credential_configured': bool(row['secret'])}

    @app.get('/healthz')
    async def health():
        db.one('SELECT 1')
        return {'status': 'ok', 'version': '0.2.0'}

    @app.get('/readyz')
    async def ready():
        state = readiness(db)
        return JSONResponse({'ready':state['ready'],'version':'0.2.0'}, status_code=200 if state['ready'] else 503)

    @app.get('/api/workspace')
    async def workspace(actor=Depends(user)):
        return {'workspace':workspace_config(db),'platforms':{key:profile(db,key) for key in PLATFORMS}}

    @app.put('/api/workspace')
    async def workspace_update(body:WorkspaceInput,actor=Depends(admin)):
        db.set_setting('workspace',body.model_dump())
        db.audit(actor['username'],'workspace.updated','workspace',body.model_dump())
        return {'ok':True}

    @app.get('/api/deployment')
    async def deployment(actor=Depends(admin)):
        return readiness(db)

    @app.put('/api/platforms/{platform}')
    async def platform_update(platform:str,body:PlatformProfile,actor=Depends(admin)):
        if platform not in PLATFORMS: raise HTTPException(404,'Unknown platform')
        db.set_setting('platform:'+platform,body.model_dump())
        db.audit(actor['username'],'platform.updated',platform,body.model_dump())
        return {'ok':True}

    @app.get('/api/auth/status')
    async def auth_status(request: Request):
        actor = None
        try:
            actor = await user(request)
        except HTTPException:
            pass
        return {'setup_required': db.one('SELECT id FROM users LIMIT 1') is None, 'user': actor}

    @app.post('/api/auth/setup')
    async def setup(body: Credentials, response: Response):
        # Setup is local-first; hosted deployments must pre-create an admin using the CLI.
        if os.environ.get('VERIFIER_DISABLE_WEB_SETUP') == '1':
            raise HTTPException(403, 'Create an administrator using the server CLI')
        with db.connect() as tx:
            tx.execute('BEGIN IMMEDIATE')
            if tx.execute('SELECT id FROM users LIMIT 1').fetchone():
                raise HTTPException(409, 'Workspace already configured')
            actor_id = uid()
            tx.execute('INSERT INTO users VALUES(?,?,?,?)', (actor_id, body.username, hash_password(body.password), 'admin'))
        session(response, actor_id)
        db.audit(body.username, 'workspace.created', actor_id)
        return {'username': body.username, 'role': 'admin'}

    @app.post('/api/auth/login')
    async def login(body: Credentials, request: Request, response: Response):
        key = request.client.host if request.client else 'unknown'
        recent = [stamp for stamp in login_attempts.get(key, []) if stamp > time.time()-300]
        if len(recent) >= 10:
            raise HTTPException(429, 'Too many sign-in attempts. Try again in five minutes.')
        login_attempts[key] = recent + [time.time()]
        row = db.one('SELECT * FROM users WHERE username=?', (body.username,))
        if not row or not verify_password(body.password, row['password']):
            raise HTTPException(401, 'Incorrect username or password')
        login_attempts.pop(key, None)
        session(response, row['id'])
        return {'username': row['username'], 'role': row['role']}

    @app.post('/api/auth/logout')
    async def logout(request: Request, response: Response, actor=Depends(user)):
        db.execute('DELETE FROM sessions WHERE digest=?', (digest(request.cookies.get('cv_session', '')),))
        response.delete_cookie('cv_session')
        return {'ok': True}

    @app.get('/api/openapi.json')
    async def schema(actor=Depends(admin)):
        return app.openapi()

    @app.get('/api/dashboard')
    async def dashboard(actor=Depends(user)):
        scope, values = ('1=1', ()) if actor['role']=='admin' else ('(is_demo=0 OR owner_id=?)', (actor['id'],))
        statuses = {row['status']: row['n'] for row in db.all('SELECT status,COUNT(*) AS n FROM cases WHERE '+scope+' GROUP BY status', values)}
        authors = db.all("SELECT DISTINCT platform,author_ref FROM cases WHERE author_verified=1 AND author_ref!=''")
        accounts = [account_state(db, row['platform'], row['author_ref']) for row in authors]
        escalations = [row for row in accounts if row['escalation'] != 'monitor']
        connections = [public_connection(row) for row in db.all('SELECT * FROM connections ORDER BY name')]
        return {'counts': statuses, 'total': sum(statuses.values()), 'escalations': escalations,
                'roles': db.all('SELECT * FROM roles'), 'connections': connections,
                'policy': db.setting('policy', DEFAULT), 'external_actions_enabled': False,
                'search_provider': db.setting('search', {'provider': 'none'})['provider']}

    @app.get('/api/cases')
    async def cases(status: str = '', q: str = '', actor=Depends(user)):
        conditions, params = [], []
        if actor['role'] != 'admin':
            conditions.append('(is_demo=0 OR owner_id=?)'); params.append(actor['id'])
        if status:
            conditions.append('status=?'); params.append(status)
        if q:
            conditions.append('(input LIKE ? OR author_ref LIKE ?)'); params.extend(['%'+q[:100]+'%']*2)
        where = ' WHERE ' + ' AND '.join(conditions) if conditions else ''
        rows = db.all('SELECT id,platform,content_id,revision,author_ref,status,stage,input,error,created,updated FROM cases' + where + ' ORDER BY created DESC LIMIT 100', params)
        for row in rows:
            content = json.loads(row.pop('input'))
            row['text'] = content['text'][:300]
        return rows

    @app.get('/api/cases/{case_id}')
    async def case_detail(case_id: str, actor=Depends(user)):
        row = find_case(case_id, actor)
        row['input'] = json.loads(row['input'])
        row['result'] = json.loads(row['result']) if row['result'] else None
        row['runs'] = db.all('SELECT * FROM runs WHERE case_id=? ORDER BY created', (case_id,))
        for run in row['runs']:
            for key in ('output', 'usage'):
                run[key] = json.loads(run[key]) if run[key] else None
        row['review'] = db.one('SELECT * FROM reviews WHERE case_id=?', (case_id,))
        row['account'] = account_state(db, row['platform'], row['author_ref']) if row['author_ref'] else None
        row['can_confirm'] = can_confirm(row) and row['status'] not in ('superseded', 'deleted')
        return row

    @app.post('/api/content-events', status_code=202)
    async def intake(body: ContentInput, actor=Depends(ingest_actor)):
        return enqueue(db, body, actor)

    @app.post('/api/cases/{case_id}/retry')
    async def retry(case_id: str, actor=Depends(user)):
        row = find_case(case_id, actor)
        if row['status'] != 'blocked':
            raise HTTPException(409, 'Only blocked cases can be retried')
        db.execute("UPDATE cases SET status='queued',stage='Waiting for agents',error=NULL,result=NULL,updated=? WHERE id=? AND status='blocked'", (now(), case_id))
        db.audit(actor['username'], 'case.retried', case_id)
        return {'ok': True}

    @app.post('/api/cases/{case_id}/decisions')
    async def decision(case_id: str, body: DecisionInput, actor=Depends(user)):
        with db.connect() as tx:
            tx.execute('BEGIN IMMEDIATE')
            current = tx.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone()
            if not current:
                raise HTTPException(404, 'Case not found')
            row = dict(current)
            if row['is_demo'] and actor['role']!='admin' and row['owner_id']!=actor['id']:
                raise HTTPException(404, 'Case not found')
            if row['status'] not in ('needs_review', 'reviewed'):
                raise HTTPException(409, 'This version is not eligible for review')
            previous = tx.execute('SELECT * FROM reviews WHERE case_id=?', (case_id,)).fetchone()
            prior = previous['decision'] if previous else None
            allowed = {None: {'confirmed','dismissed'}, 'confirmed': {'appealed','overturned'}, 'appealed': {'confirmed','overturned'}, 'dismissed': set(), 'overturned': set()}
            if body.decision not in allowed.get(prior, set()):
                raise HTTPException(409, 'Invalid review transition')
            if body.decision == 'confirmed':
                if not can_confirm(row) or not body.policy_rule or not body.incident_key:
                    raise HTTPException(422, 'Confirmation needs cited adverse findings, a verified author, policy rule and distinct incident key')
            incident = body.incident_key or (previous['incident_key'] if previous else '')
            rule = body.policy_rule or (previous['policy_rule'] if previous else '')
            tx.execute('INSERT INTO reviews VALUES(?,?,?,?,?,?,?) ON CONFLICT(case_id) DO UPDATE SET decision=excluded.decision,reason=excluded.reason,policy_rule=excluded.policy_rule,incident_key=excluded.incident_key,reviewer=excluded.reviewer,updated=excluded.updated',
                       (case_id, body.decision, body.reason, rule, incident, actor['username'], now()))
            tx.execute("UPDATE cases SET status='reviewed',stage=?,updated=? WHERE id=?", (body.decision, now(), case_id))
        db.audit(actor['username'], 'review.'+body.decision, case_id, {'reason': body.reason, 'policy_rule': rule, 'incident_key': incident, 'previous': prior})
        return {'decision': body.decision, 'account': account_state(db, row['platform'], row['author_ref']), 'external_action': None}

    @app.get('/api/connections')
    async def connections(actor=Depends(admin)):
        search = db.setting('search', {'provider': 'none'})
        return {'connections': [public_connection(row) for row in db.all('SELECT * FROM connections ORDER BY name')],
                'roles': db.all('SELECT * FROM roles'), 'search': {'provider': search['provider'], 'credential_configured': bool(search.get('secret'))}}

    @app.post('/api/connections')
    async def connection_create(body: ConnectionInput, actor=Depends(admin)):
        try:
            parts = validate_url(body.base_url, body.local_endpoint)
            if not body.local_endpoint and parts.scheme != 'https':
                raise NetworkError('Hosted model endpoints require HTTPS')
            if parts.query or parts.fragment:
                raise NetworkError('Connection endpoints must not contain query strings or fragments')
            await pinned_url(body.base_url, body.local_endpoint)
        except NetworkError as exc:
            raise HTTPException(422, str(exc)) from None
        identifier = uid()
        db.execute('INSERT INTO connections VALUES(?,?,?,?,?,?,?)', (identifier, body.name, body.kind, body.base_url.rstrip('/'), body.model, vault.encrypt(body.api_key), int(body.local_endpoint)))
        for role in ROLES:
            db.execute('INSERT OR IGNORE INTO roles VALUES(?,?,NULL)', (role, identifier))
        db.audit(actor['username'], 'connection.created', identifier, {'kind': body.kind, 'model': body.model})
        return {'id': identifier}

    @app.delete('/api/connections/{identifier}')
    async def connection_delete(identifier: str, actor=Depends(admin)):
        if db.one('SELECT role FROM roles WHERE connection_id=? OR fallback_id=?', (identifier, identifier)):
            raise HTTPException(409, 'Reassign agents before removing their connection')
        db.execute('DELETE FROM connections WHERE id=?', (identifier,))
        db.audit(actor['username'], 'connection.deleted', identifier)
        return {'ok': True}

    @app.post('/api/connections/{identifier}/test')
    async def connection_test(identifier: str, actor=Depends(admin)):
        from pydantic import BaseModel
        class Probe(BaseModel):
            ok: bool
        connection = db.one('SELECT * FROM connections WHERE id=?', (identifier,))
        if not connection:
            raise HTTPException(404, 'Connection not found')
        started = time.monotonic()
        try:
            value, usage = await providers.complete(connection, 'probe', 'Return the JSON object {"ok":true}.', {'purpose': 'Connection test only'}, Probe.model_json_schema())
            if value.get('ok') is not True:
                raise ProviderError('The model did not return the required probe response')
        except (ProviderError, NetworkError) as exc:
            raise HTTPException(422, str(exc)) from None
        db.audit(actor['username'], 'connection.tested', identifier)
        return {'ok': True, 'elapsed_ms': int((time.monotonic()-started)*1000), 'usage': usage}

    @app.put('/api/agents/{role}')
    async def agent_update(role: str, body: RoleInput, actor=Depends(admin)):
        if role not in ROLES:
            raise HTTPException(404, 'Unknown agent role')
        for identifier in (body.connection_id, body.fallback_id):
            if identifier and not db.one('SELECT id FROM connections WHERE id=?', (identifier,)):
                raise HTTPException(422, 'Connection not found')
        db.execute('INSERT INTO roles VALUES(?,?,?) ON CONFLICT(role) DO UPDATE SET connection_id=excluded.connection_id,fallback_id=excluded.fallback_id', (role, body.connection_id, body.fallback_id))
        db.audit(actor['username'], 'agent.updated', role, body.model_dump())
        return {'ok': True}

    @app.put('/api/search')
    async def search_update(body: SearchInput, actor=Depends(admin)):
        existing = db.setting('search', {})
        secret = vault.encrypt(body.api_key) if body.api_key else existing.get('secret', '')
        if body.provider == 'tavily' and not secret:
            raise HTTPException(422, 'A Tavily API key is required')
        db.set_setting('search', {'provider': body.provider, 'secret': secret})
        db.audit(actor['username'], 'search.updated', body.provider)
        return {'ok': True}

    @app.put('/api/policy')
    async def policy_update(body: PolicyInput, actor=Depends(admin)):
        if body.senior_threshold <= body.admin_threshold:
            raise HTTPException(422, 'Senior threshold must be above the admin threshold')
        db.set_setting('policy', body.model_dump())
        db.audit(actor['username'], 'policy.updated', 'workspace', body.model_dump())
        return {'ok': True}

    @app.get('/api/tokens')
    async def tokens(actor=Depends(admin)):
        return db.all('SELECT id,name,created FROM tokens ORDER BY created DESC')

    @app.post('/api/tokens')
    async def token_create(body: TokenInput, actor=Depends(admin)):
        token, identifier = 'cv_' + secrets.token_urlsafe(32), uid()
        db.execute('INSERT INTO tokens VALUES(?,?,?,?)', (digest(token), identifier, body.name, now()))
        db.audit(actor['username'], 'integration.created', identifier)
        return {'id': identifier, 'token': token, 'scope': 'content-events:write', 'shown_once': True}

    @app.delete('/api/tokens/{identifier}')
    async def token_delete(identifier: str, actor=Depends(admin)):
        db.execute('DELETE FROM tokens WHERE id=?', (identifier,))
        db.audit(actor['username'], 'integration.revoked', identifier)
        return {'ok': True}

    @app.get('/api/audit')
    async def audit(actor=Depends(admin)):
        rows = db.all('SELECT * FROM audit ORDER BY id DESC LIMIT 200')
        for row in rows:
            row['details'] = json.loads(row['details'])
        return rows

    @app.get('/api/cases/{case_id}/export')
    async def export(case_id: str, actor=Depends(user)):
        value = await case_detail(case_id, actor)
        return JSONResponse(value, headers={'Content-Disposition': f'attachment; filename="case-{case_id}.json"'})

    app.mount('/assets', StaticFiles(directory=STATIC), name='assets')
    app.include_router(social_router(social,user,admin))

    @app.get('/')
    async def index():
        return FileResponse(STATIC / 'index.html')

    return app
