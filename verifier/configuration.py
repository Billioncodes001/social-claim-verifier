"""Customer settings and deployment readiness; no model or platform secrets."""
import os
from pathlib import Path
from .models import WorkspaceInput, PlatformProfile, ROLES
from .db import uid
from .security import hash_password

PLATFORMS = {'x':'X / Twitter','facebook':'Facebook','instagram':'Instagram','whatsapp':'WhatsApp','partner_feed':'Partner platform','rss':'RSS','manual':'Manual research'}

def workspace_config(db):
    return db.setting('workspace', WorkspaceInput().model_dump())

def profile(db, platform):
    return db.setting('platform:'+platform, PlatformProfile(display_name=PLATFORMS[platform]).model_dump())

def queue_limit():
    return max(1, min(10000, int(os.environ.get('VERIFIER_QUEUE_LIMIT', '100'))))

def worker_count():
    return max(1, min(16, int(os.environ.get('VERIFIER_WORKERS', '2'))))

def bootstrap(db):
    """One-time container bootstrap from a mounted secret, never a baked password."""
    password_file = os.environ.get('VERIFIER_BOOTSTRAP_PASSWORD_FILE')
    if not password_file or db.one('SELECT id FROM users LIMIT 1'):
        return
    password = Path(password_file).read_text(encoding='utf-8').strip()
    username = os.environ.get('VERIFIER_BOOTSTRAP_USERNAME', 'admin')
    if not 12 <= len(password) <= 256 or not 3 <= len(username) <= 80:
        raise RuntimeError('Bootstrap credentials do not meet the required length')
    with db.connect() as tx:
        tx.execute('BEGIN IMMEDIATE')
        if not tx.execute('SELECT id FROM users LIMIT 1').fetchone():
            tx.execute('INSERT INTO users VALUES(?,?,?,?)', (uid(),username,hash_password(password),'admin'))
    db.audit('bootstrap', 'workspace.bootstrapped', 'workspace')

def readiness(db):
    roles = db.all('SELECT role,connection_id FROM roles')
    assigned = {row['role'] for row in roles if db.one('SELECT id FROM connections WHERE id=?',(row['connection_id'],))}
    public = os.environ.get('VERIFIER_PUBLIC_URL','http://127.0.0.1:8791').rstrip('/')
    checks = [
        {'id':'database','label':'Persistent database available','ok':bool(db.one('SELECT 1')),'required':True},
        {'id':'admin','label':'Administrator created','ok':bool(db.one("SELECT id FROM users WHERE role='admin'")),'required':True},
        {'id':'agents','label':'All four agents assigned','ok':set(ROLES)<=assigned,'required':True},
        {'id':'search','label':'Evidence search configured (optional with source URLs)','ok':db.setting('search',{'provider':'none'})['provider']!='none','required':False},
        {'id':'https','label':'HTTPS public URL configured','ok':public.startswith('https://'),'required':False},
        {'id':'cookies','label':'Secure cookies enabled for hosting','ok':os.environ.get('VERIFIER_SECURE_COOKIES')=='1','required':False},
        {'id':'setup','label':'Public web setup disabled','ok':os.environ.get('VERIFIER_DISABLE_WEB_SETUP')=='1','required':False},
    ]
    return {'ready':all(check['ok'] for check in checks if check['required']), 'checks':checks,
            'public_url':public,'worker_count':worker_count(),'queue_limit':queue_limit(),
            'deployment_model':'One isolated customer workspace per service instance',
            'assessment':'Configuration readiness only; provider tests and commercial acceptance are separate.'}
