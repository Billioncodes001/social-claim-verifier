import importlib.util
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from verifier.app import create_app
from verifier.db import Database,uid
from verifier.initialize import initialize
from verifier.security import Vault,hash_password,verify_password


def generator():
    spec=importlib.util.spec_from_file_location('deploy',Path(__file__).resolve().parents[1]/'scripts/deploy.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.build_bundle


def test_generated_installation_bootstraps_once_and_preserves_key(tmp_path,monkeypatch):
    bundle=generator()(tmp_path/'install')
    secret=bundle/'secrets/admin_password'
    key=bundle/'secrets/master_key'
    config=json.loads((bundle/'compose.yaml').read_text())
    assert config['services']['initialize']['network_mode']=='none'
    assert config['services']['verifier']['cap_drop']==['ALL']
    assert config['services']['verifier']['ports']==['127.0.0.1:8791:8791']
    assert secret.read_text().strip() not in (bundle/'compose.yaml').read_text()
    monkeypatch.setenv('VERIFIER_BOOTSTRAP_PASSWORD_FILE',str(secret))
    monkeypatch.setenv('VERIFIER_DISABLE_WEB_SETUP','1')
    data=tmp_path/'data'
    db=initialize(data,key)
    saved=db.one('SELECT * FROM users')
    assert verify_password(secret.read_text().strip(),saved['password'])
    encrypted=Vault(data).encrypt('customer-provider-key')
    secret.write_text('a-different-bootstrap-password')
    initialize(data,key)
    assert db.one('SELECT * FROM users')==saved
    assert Vault(data).decrypt(encrypted)=='customer-provider-key'
    with TestClient(create_app(data,run_workers=False)) as client:
        assert client.get('/api/auth/status').json()['setup_required'] is False
        assert client.post('/api/auth/setup',json={'username':'stranger','password':'unwanted-new-password'}).status_code==403
    key.write_bytes(b'eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHg=')
    with pytest.raises(RuntimeError,match='differs'):initialize(data,key)
    with pytest.raises(FileExistsError):generator()(bundle)


def test_https_install_and_host_validation(tmp_path):
    bundle=generator()(tmp_path/'https',domain='claims.example.com')
    config=json.loads((bundle/'compose.yaml').read_text())
    app=config['services']['verifier']
    assert 'ports' not in app
    assert app['environment']['VERIFIER_SECURE_COOKIES']=='1'
    assert app['environment']['VERIFIER_PUBLIC_URL']=='https://claims.example.com'
    assert config['services']['https']['ports']==['80:80','443:443']
    for domain in ('https://claims.example.com','evil.example.com\n{ }','claims.example.com:80','*.example.com'):
        with pytest.raises(ValueError):generator()(tmp_path/'invalid',domain=domain)
    assert not (tmp_path/'invalid').exists()


def test_platform_configuration_enforces_intake_and_privacy(workspace,event):
    app,client=workspace
    assert client.get('/readyz').status_code==503
    assert client.put('/api/workspace',json={'name':'Customer trust desk','organization':'Example organization','demo_daily_limit':3}).status_code==200
    assert client.get('/api/workspace').json()['workspace']['name']=='Customer trust desk'
    assert client.put('/api/platforms/x',json={'display_name':'Our X channel','allow_hosted':False,'allow_search':False,'policy':{'window_days':30,'admin_threshold':3,'senior_threshold':5}}).status_code==200
    assert client.post('/api/content-events',json={**event,'allow_external_processing':True}).status_code==403
    assert client.post('/api/content-events',json={**event,'allow_web_search':True}).status_code==403
    assert client.post('/api/content-events',json=event).status_code==202
    assert client.put('/api/platforms/x',json={'display_name':'X','enabled':False}).status_code==200
    assert client.post('/api/content-events',json={**event,'event_id':'new','content_id':'new'}).status_code==403
    assert client.put('/api/platforms/x',json={'display_name':'X','policy':{'admin_threshold':5,'senior_threshold':3}}).status_code==422
    app.state.db.execute('INSERT INTO users VALUES(?,?,?,?)',(uid(),'reviewer',hash_password('reviewer-config-test'),'reviewer'))
    with TestClient(app) as reviewer:
        reviewer.post('/api/auth/login',json={'username':'reviewer','password':'reviewer-config-test'})
        assert reviewer.put('/api/workspace',json={'name':'Unapproved'}).status_code==403
        assert reviewer.get('/api/deployment').status_code==403
        assert reviewer.get('/api/social/apps').status_code==403


def test_v1_schema_migrates_existing_cases(workspace,event):
    app,client=workspace
    identifier=client.post('/api/content-events',json=event).json()['case_id']
    with app.state.db.connect() as tx:
        tx.execute('DROP INDEX cases_demo_owner')
        tx.execute('ALTER TABLE cases DROP COLUMN is_demo')
        tx.execute('ALTER TABLE cases DROP COLUMN owner_id')
        tx.execute('PRAGMA user_version=1')
    reopened=Database(app.state.db.root)
    case=reopened.one('SELECT * FROM cases WHERE id=?',(identifier,))
    assert case['is_demo']==0 and case['owner_id'] is None
    assert json.loads(case['input'])['text']==event['text']
    assert reopened.one('PRAGMA user_version')['user_version']==2
