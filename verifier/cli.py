import argparse
import getpass
import os
from pathlib import Path
import uvicorn
from .db import Database, uid
from .security import hash_password

def main():
    parser = argparse.ArgumentParser(description='Run the Claim Verifier review workspace')
    sub = parser.add_subparsers(dest='command', required=True)
    serve = sub.add_parser('serve')
    serve.add_argument('--host', default='127.0.0.1')
    serve.add_argument('--port', type=int, default=8791)
    serve.add_argument('--data-dir', default='.runtime')
    create = sub.add_parser('create-user')
    create.add_argument('--username', required=True)
    create.add_argument('--role', choices=['admin','reviewer'], default='reviewer')
    create.add_argument('--data-dir', default='.runtime')
    reset = sub.add_parser('reset-password')
    reset.add_argument('--username', required=True)
    reset.add_argument('--data-dir', default='.runtime')
    args = parser.parse_args()
    if args.command == 'serve':
        os.environ['VERIFIER_DATA_DIR'] = str(Path(args.data_dir).resolve())
        uvicorn.run('verifier.app:create_app', factory=True, host=args.host, port=args.port, workers=1)
    else:
        password = getpass.getpass('Password (12+ characters): ')
        if len(password) < 12:
            parser.error('Use at least 12 characters')
        db = Database(Path(args.data_dir).resolve())
        if args.command == 'create-user':
            db.execute('INSERT INTO users VALUES(?,?,?,?)', (uid(),args.username,hash_password(password),args.role))
            print('User created.')
        else:
            actor = db.one('SELECT id FROM users WHERE username=?', (args.username,))
            if not actor: parser.error('User not found')
            with db.connect() as tx:
                tx.execute('UPDATE users SET password=? WHERE id=?', (hash_password(password),actor['id']))
                tx.execute('DELETE FROM sessions WHERE user_id=?', (actor['id'],))
            db.audit('server-cli', 'user.password_reset', actor['id'])
            print('Password updated; previous sessions revoked.')

if __name__ == '__main__': main()
