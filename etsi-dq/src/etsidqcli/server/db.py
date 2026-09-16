"""SQLite database."""
import sqlite3, uuid, json
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("etsidqcli_server.db")
_conn = None

def get_conn():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, name TEXT, org TEXT, api_key TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, dataset_name TEXT, dataset_hash TEXT, overall_score REAL, overall_grade TEXT, metrics_json TEXT, profile_json TEXT, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS certificates (id TEXT PRIMARY KEY, certificate_key TEXT UNIQUE NOT NULL, report_id TEXT NOT NULL, user_id TEXT NOT NULL, issued_at TEXT NOT NULL, status TEXT DEFAULT 'valid');
        """)
        _conn.commit()
    return _conn

def create_user(name, org=""):
    c = get_conn(); uid = uuid.uuid4().hex[:8]; key = f"DQ-{uuid.uuid4().hex[:16].upper()}"; now = datetime.now(timezone.utc).isoformat()
    c.execute("INSERT INTO users VALUES (?,?,?,?,?)", (uid, name, org, key, now)); c.commit()
    return {"user_id": uid, "name": name, "org": org, "api_key": key}

def get_user_by_key(api_key):
    r = get_conn().execute("SELECT * FROM users WHERE api_key=?", (api_key,)).fetchone()
    return dict(r) if r else None

def create_report(user_id, dataset_name, dataset_hash, overall_score, overall_grade, metrics, profile):
    c = get_conn(); rid = uuid.uuid4().hex[:8]; now = datetime.now(timezone.utc).isoformat()
    c.execute("INSERT INTO reports VALUES (?,?,?,?,?,?,?,?,?)", (rid, user_id, dataset_name, dataset_hash, overall_score, overall_grade, json.dumps(metrics), json.dumps(profile), now)); c.commit()
    return {"report_id": rid, "created_at": now}

def get_reports_by_user(user_id, limit=50):
    return [dict(r) for r in get_conn().execute("SELECT * FROM reports WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id, limit)).fetchall()]

def issue_certificate(report_id, user_id):
    c = get_conn(); cid = uuid.uuid4().hex[:8]; now = datetime.now(timezone.utc).isoformat()
    key = f"DQ-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:6].upper()}"
    c.execute("INSERT INTO certificates VALUES (?,?,?,?,?,?)", (cid, key, report_id, user_id, now, "valid")); c.commit()
    return {"certificate_key": key, "issued_at": now}

def verify_certificate(cert_key):
    r = get_conn().execute("SELECT c.*, r.dataset_name, r.overall_score, r.overall_grade, r.metrics_json, r.created_at as evaluated_at, u.name as user_name, u.org FROM certificates c JOIN reports r ON c.report_id=r.id JOIN users u ON c.user_id=u.id WHERE c.certificate_key=?", (cert_key,)).fetchone()
    return dict(r) if r else None
