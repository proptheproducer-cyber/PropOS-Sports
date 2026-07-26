#!/usr/bin/env python3
"""
Cartella ingest endpoint for PROP PRIME.

A tiny, dependency-free HTTP service that gives the Cartella agent a safe way to
write a recognized task into the "brain" (prime2.json). Cartella does the
understanding (it's an LLM on Telegram); this endpoint does the filing:

  - matches the task to an existing project by name (fuzzy), or creates one
  - appends the task into that project's nested tasks[] as a PENDING item
    (added:"Cartella"), so the app shows it in the yellow approval card
  - writes prime2.json atomically, under a file lock, in the exact shape the
    app already reads (projects[].tasks[] + a flat tasks[] mirror)

It intentionally does NOT touch pomodoro/galaxy/save-render logic — it only
edits the JSON file the app loads.

Env:
  PRIME_JSON       path to prime2.json         (default /var/www/prop/prime2.json)
  CARTELLA_TOKEN   shared secret; callers must send it as X-Cartella-Token
  HOST             bind host                    (default 127.0.0.1)
  PORT             bind port                    (default 8787)

Request (POST, JSON), single task:
  {"task":"Follow up with Marcus Wright","project":"Follow ups",
   "importance":"high","pomos":1,"len":25}
Or a batch:
  {"tasks":[{"task":"...","project":"..."}, ...]}

Response: {"ok":true,"added":[{"project":"Follow ups","task":"..."}]}
"""
import json, os, time, fcntl, tempfile, random, string
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PRIME_JSON = os.environ.get("PRIME_JSON", "/var/www/prop/prime2.json")
TOKEN      = os.environ.get("CARTELLA_TOKEN", "")
HOST       = os.environ.get("HOST", "127.0.0.1")
PORT       = int(os.environ.get("PORT", "8787"))
LOCK_PATH  = PRIME_JSON + ".lock"

# importance -> default number of pomodoro slots (only used when pomos omitted)
IMPORTANCE_POMOS = {"low": 1, "medium": 2, "med": 2, "normal": 2, "high": 3, "urgent": 4}
VALID_LENS = {15, 25, 30, 45, 60}


def uid():
    return "x" + format(int(time.time() * 1000), "x") + "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(3))


def num(v, d):
    try:
        n = int(float(v))
        return n if n >= 0 else d
    except Exception:
        return d


def load_state():
    try:
        with open(PRIME_JSON, "r") as f:
            data = json.load(f)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("projects", [])
    data.setdefault("tasks", [])
    data.setdefault("log", {})
    if not isinstance(data["projects"], list):
        data["projects"] = []
    return data


def flat_mirror(projects):
    """Rebuild the flat tasks[] mirror the app writes, so the file shape stays
    identical to what the app itself PUTs."""
    out = []
    for p in projects:
        for t in (p.get("tasks") or []):
            row = dict(t)
            row["projId"] = p.get("id")
            row["planet"] = p.get("planet")
            out.append(row)
    return out


def atomic_write(data):
    body = json.dumps(data, indent=2)
    d = os.path.dirname(PRIME_JSON) or "."
    try:
        fd, tmp = tempfile.mkstemp(prefix=".prime2.", dir=d)
        with os.fdopen(fd, "w") as f:
            f.write(body)
        try:
            st = os.stat(PRIME_JSON)
            os.chmod(tmp, st.st_mode)
            os.chown(tmp, st.st_uid, st.st_gid)  # keep www-data ownership
        except Exception:
            pass
        os.replace(tmp, PRIME_JSON)  # atomic for readers (nginx/app)
    except Exception:
        # Fallback: in-place write if the directory isn't writable for rename
        with open(PRIME_JSON, "w") as f:
            f.write(body)


def find_project(projects, name):
    if not name:
        return None
    key = name.strip().lower()
    # exact (case-insensitive) first, then contains either direction
    for p in projects:
        if (p.get("name") or "").strip().lower() == key:
            return p
    for p in projects:
        pn = (p.get("name") or "").strip().lower()
        if pn and (key in pn or pn in key):
            return p
    return None


def make_task(item):
    name = (item.get("task") or item.get("name") or item.get("title") or "").strip()
    if not name:
        return None
    pomos = item.get("pomos")
    if pomos is None:
        pomos = IMPORTANCE_POMOS.get(str(item.get("importance", "")).lower(), 1)
    ln = num(item.get("len"), 25)
    if ln not in VALID_LENS:
        ln = 25
    pending = item.get("pending", True)
    return {
        "id": uid(),
        "name": name,
        "pomos": max(1, num(pomos, 1)),
        "len": ln,
        "done": 0,
        "complete": False,
        "pending": bool(pending),
        "added": item.get("added") or "Cartella",
    }


def ingest(items):
    """Read-modify-write prime2.json under an exclusive lock. Returns list of
    {project, task} that were added."""
    added = []
    lock = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = load_state()
        projects = data["projects"]
        for item in items:
            task = make_task(item)
            if not task:
                continue
            pname = item.get("project") or item.get("projectName") or item.get("section")
            proj = find_project(projects, pname)
            if not proj:
                proj = {
                    "id": "p_" + uid(),
                    "planet": (item.get("planet") or "business"),
                    "name": (pname.strip() if pname else "Inbox"),
                    "tasks": [],
                }
                projects.append(proj)
            proj.setdefault("tasks", [])
            proj["tasks"].append(task)
            added.append({"project": proj["name"], "task": task["name"], "id": task["id"]})
        data["tasks"] = flat_mirror(projects)  # keep flat mirror in sync
        atomic_write(data)
    finally:
        try:
            fcntl.flock(lock, fcntl.LOCK_UN)
        finally:
            lock.close()
    return added


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass  # quiet; systemd/journald captures stdout if needed

    def do_GET(self):
        # simple health check
        self._send(200, {"ok": True, "service": "cartella-ingest"})

    def do_POST(self):
        if TOKEN and self.headers.get("X-Cartella-Token") != TOKEN:
            self._send(401, {"ok": False, "error": "bad or missing X-Cartella-Token"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b""
            payload = json.loads(raw or b"{}")
        except Exception as e:
            self._send(400, {"ok": False, "error": "invalid JSON: %s" % e})
            return
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload.get("tasks"), list):
            items = payload["tasks"]
        else:
            items = [payload]
        try:
            added = ingest(items)
        except Exception as e:
            self._send(500, {"ok": False, "error": str(e)})
            return
        if not added:
            self._send(422, {"ok": False, "error": "no valid task found (need a 'task' field)"})
            return
        self._send(200, {"ok": True, "added": added})


def main():
    if not TOKEN:
        print("WARNING: CARTELLA_TOKEN is empty — the endpoint is UNAUTHENTICATED. "
              "Set CARTELLA_TOKEN before exposing it.", flush=True)
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print("cartella-ingest listening on %s:%d -> %s" % (HOST, PORT, PRIME_JSON), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
