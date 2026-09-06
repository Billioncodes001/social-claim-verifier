import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

def now():
    return datetime.now(timezone.utc).isoformat()

def uid():
    return uuid.uuid4().hex

def dumps(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)

class Database:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / 'verifier.sqlite3'
        self.lock = threading.RLock()
        with self.connect() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(digest TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS tokens(digest TEXT PRIMARY KEY, id TEXT UNIQUE, name TEXT, created TEXT);
            CREATE TABLE IF NOT EXISTS connections(id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL,base_url TEXT NOT NULL,model TEXT NOT NULL,secret TEXT NOT NULL,local_endpoint INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS roles(role TEXT PRIMARY KEY, connection_id TEXT NOT NULL, fallback_id TEXT);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY, platform TEXT NOT NULL,content_id TEXT NOT NULL,revision INTEGER NOT NULL,author_ref TEXT NOT NULL,author_verified INTEGER NOT NULL,status TEXT NOT NULL,stage TEXT NOT NULL,input TEXT NOT NULL,result TEXT,error TEXT,created TEXT NOT NULL,updated TEXT NOT NULL,UNIQUE(platform,content_id,revision));
            CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY, digest TEXT NOT NULL,case_id TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,role TEXT NOT NULL,status TEXT NOT NULL,connection_id TEXT,model TEXT,output TEXT,usage TEXT,elapsed_ms INTEGER,error TEXT,created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reviews(case_id TEXT PRIMARY KEY,decision TEXT NOT NULL,reason TEXT NOT NULL,policy_rule TEXT NOT NULL,incident_key TEXT NOT NULL,reviewer TEXT NOT NULL,updated TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,actor TEXT NOT NULL,action TEXT NOT NULL,subject TEXT NOT NULL,details TEXT NOT NULL,created TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS cases_status ON cases(status,created);
            CREATE INDEX IF NOT EXISTS cases_author ON cases(platform,author_ref);
            CREATE INDEX IF NOT EXISTS runs_case ON runs(case_id,created);
            ''')

    @contextmanager
    def connect(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=30)
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
            finally:
                db.close()

    def all(self, query, values=()):
        with self.connect() as db:
            return [dict(row) for row in db.execute(query, values).fetchall()]

    def one(self, query, values=()):
        rows = self.all(query, values)
        return rows[0] if rows else None

    def execute(self, query, values=()):
        with self.connect() as db:
            return db.execute(query, values).rowcount

    def setting(self, key, default=None):
        row = self.one('SELECT value FROM settings WHERE key=?', (key,))
        return json.loads(row['value']) if row else default

    def set_setting(self, key, value):
        self.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, dumps(value)))

    def audit(self, actor, action, subject, details=None):
        self.execute('INSERT INTO audit(actor,action,subject,details,created) VALUES(?,?,?,?,?)', (actor, action, subject, dumps(details or {}), now()))

    def claim_job(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM cases WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if row:
                db.execute("UPDATE cases SET status='processing',stage='Starting agents',updated=? WHERE id=?", (now(), row['id']))
                return dict(row)

    def recover(self):
        with self.connect() as db:
            db.execute("UPDATE cases SET status='queued',stage='Recovered after restart' WHERE status='processing'")
            db.execute("UPDATE runs SET status='interrupted',error='Worker restarted' WHERE status='running'")
