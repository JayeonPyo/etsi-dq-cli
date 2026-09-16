"""Server communication client."""
import hashlib, json
from pathlib import Path
from etsidqcli import auth

def _hash(path):
    if path is None: return "dataframe"
    p = Path(path)
    if not p.exists(): return "unknown"
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""): h.update(chunk)
    return h.hexdigest()[:16]

def submit_result(result, data_source=None):
    key = auth.get_key()
    if not key: return None
    payload = {"api_key": key, "dataset_hash": _hash(data_source), "dataset_name": Path(data_source).name if data_source else "dataframe",
        "overall_score": result.overall_score, "overall_grade": result.overall_grade,
        "metrics": {n: {"score": m.score, "grade": m.grade, "passed": m.passed} for n, m in result.metrics.items() if m.score is not None},
        "profile": {"row_count": result.profile.row_count, "column_count": result.profile.column_count}}
    try:
        import urllib.request
        req = urllib.request.Request(f"{auth.get_server()}/api/reports/submit", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp: return json.loads(resp.read())
    except: return None

def verify_certificate(cert_key):
    try:
        import urllib.request
        with urllib.request.urlopen(f"{auth.get_server()}/api/certificates/{cert_key}/verify", timeout=10) as resp: return json.loads(resp.read())
    except: return None
