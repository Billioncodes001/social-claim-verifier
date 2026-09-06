import hashlib
import hmac
import os
import secrets
from pathlib import Path
from cryptography.fernet import Fernet

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def hash_password(password):
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600000)
    return salt.hex() + ':' + derived.hex()

def verify_password(password, encoded):
    try:
        salt, expected = encoded.split(':')
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000)
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False

class Vault:
    def __init__(self, root: Path):
        path = root / 'master.key'
        supplied = os.environ.get('VERIFIER_MASTER_KEY')
        if supplied:
            key = supplied.encode()
        else:
            if not path.exists():
                try:
                    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    with os.fdopen(fd, 'wb') as handle:
                        handle.write(Fernet.generate_key())
                except FileExistsError:
                    pass
            key = path.read_bytes().strip()
        self.box = Fernet(key)

    def encrypt(self, value):
        return self.box.encrypt(value.encode()).decode() if value else ''

    def decrypt(self, value):
        return self.box.decrypt(value.encode()).decode() if value else ''
