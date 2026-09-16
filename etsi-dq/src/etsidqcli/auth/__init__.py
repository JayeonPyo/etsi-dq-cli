"""API key management."""
import json
from pathlib import Path
CONFIG_DIR = Path.home() / ".etsi-dq"
CONFIG_FILE = CONFIG_DIR / "credentials.json"

def _load():
    if not CONFIG_FILE.exists(): return {}
    try: return json.loads(CONFIG_FILE.read_text())
    except: return {}

def _save(data):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2))

def set_key(k): d = _load(); d["api_key"] = k; _save(d)
def get_key(): return _load().get("api_key")
def set_server(url): d = _load(); d["server_url"] = url.rstrip("/"); _save(d)
def get_server(): return _load().get("server_url", "http://localhost:8000")
def clear():
    if CONFIG_FILE.exists(): CONFIG_FILE.unlink()
