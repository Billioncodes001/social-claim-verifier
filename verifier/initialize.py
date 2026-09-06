"""One-shot container provisioning from mounted secrets; network access is unnecessary."""
import os
from pathlib import Path
from cryptography.fernet import Fernet
from .configuration import bootstrap
from .db import Database


def initialize(root, key_file, *, owner=None):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    key = Path(key_file).read_bytes().strip()
    Fernet(key)  # Validate before touching the persistent volume.
    target = root / 'master.key'
    if target.is_symlink():
        raise RuntimeError('The master key must be a regular file')
    if target.exists():
        if target.read_bytes().strip() != key:
            raise RuntimeError('Mounted key differs from the existing volume key; restore the matching secret')
    else:
        with target.open('xb') as handle:
            handle.write(key)
        target.chmod(0o600)
    db = Database(root)
    bootstrap(db)
    if not db.one("SELECT id FROM users WHERE role='admin'"):
        raise RuntimeError('No administrator exists; supply a valid bootstrap password secret')
    if owner is not None and hasattr(os, 'chown'):
        # Only our known volume entries, never a recursive ownership change.
        for path in [root, target, db.path, root/'verifier.sqlite3-wal', root/'verifier.sqlite3-shm']:
            if path.exists():
                if path.is_symlink():
                    raise RuntimeError('Unexpected symbolic link in the data volume')
                os.chown(path, *owner)
        root.chmod(0o700)
    return db


if __name__ == '__main__':
    initialize(os.environ.get('VERIFIER_DATA_DIR','/data'),
               os.environ.get('VERIFIER_MASTER_KEY_FILE','/run/secrets/master_key'), owner=(10001,10001))
    print('Workspace initialized; existing credentials and data preserved.')
