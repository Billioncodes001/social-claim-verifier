"""Create a local model credential and assign unconfigured agents. No user creation."""
import secrets
from pathlib import Path
from verifier.db import Database, uid
from verifier.models import ROLES
from verifier.security import Vault

root=Path(__file__).resolve().parents[1]/'.runtime'
db, vault=Database(root), Vault(root)
keyfile=root/'local-model'/'api.key'
if not keyfile.exists():
    keyfile.parent.mkdir(parents=True,exist_ok=True)
    keyfile.write_text(secrets.token_urlsafe(40),encoding='utf-8')
existing=db.one("SELECT id FROM connections WHERE name='Local Qwen · development'")
identifier=existing['id'] if existing else uid()
secret=vault.encrypt(keyfile.read_text(encoding='utf-8').strip())
db.execute('INSERT INTO connections VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET secret=excluded.secret',
           (identifier,'Local Qwen · development','openai_chat','http://127.0.0.1:8087/v1','qwen3-4b-local',secret,1))
for role in ROLES:
    db.execute('INSERT OR IGNORE INTO roles VALUES(?,?,NULL)',(role,identifier))
print('Local model configured. Credentials remain on this computer.')
