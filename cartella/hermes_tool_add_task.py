"""
Reference implementation of the Cartella -> PROP PRIME tool for Hermes Agent.

This is the *body* of the tool (framework-agnostic, stdlib only). Register it in
Hermes using whatever tool/skill format hermes-gateway uses — the function,
its docstring, and the three parameters map directly onto a tool schema:

    name:        add_task_to_prime
    description: (the docstring)
    params:      task (required, str), project (str), importance (enum)

Because Hermes runs on the same VPS as the ingest endpoint, this calls it over
localhost. Set these in the hermes-gateway service environment (same secret you
put in cartella-ingest.service):

    CARTELLA_INGEST_URL=http://127.0.0.1:8787/prime/ingest   (this is the default)
    CARTELLA_TOKEN=<the same secret as cartella-ingest>
"""
import os
import json
import urllib.request
import urllib.error

INGEST_URL = os.environ.get("CARTELLA_INGEST_URL", "http://127.0.0.1:8787/prime/ingest")
INGEST_TOKEN = os.environ.get("CARTELLA_TOKEN", "")


def add_task_to_prime(task, project=None, importance="medium"):
    """File a task the user needs to do into PROP PRIME (the brain).

    Call this whenever the user mentions an action item, follow-up, reminder, or
    appointment. Pick `project` from the user's existing sections (e.g.
    "Follow ups"); omit it if unsure and it lands in Inbox. Set `importance`
    from urgency and client value.

    Args:
        task: The action item, in imperative phrasing (e.g. "Follow up with Marcus Wright").
        project: Existing section name to file it under, or None for Inbox.
        importance: one of "low", "medium", "high", "urgent".

    Returns:
        A short human-readable confirmation string to relay back to the user.
    """
    task = (task or "").strip()
    if not task:
        return "I couldn't file that — no task text was given."

    payload = {"task": task, "importance": importance or "medium"}
    if project:
        payload["project"] = project

    req = urllib.request.Request(
        INGEST_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Cartella-Token": INGEST_TOKEN,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        return "Couldn't file the task (HTTP %s): %s" % (e.code, detail)
    except Exception as e:
        return "Couldn't reach PROP PRIME: %s" % e

    if res.get("ok") and res.get("added"):
        a = res["added"][0]
        return "Filed “%s” into %s — it's waiting in your approval card." % (
            a.get("task"), a.get("project"))
    return "Nothing was filed: %s" % res.get("error", "unknown error")


# Manual smoke test:  CARTELLA_TOKEN=... python3 hermes_tool_add_task.py "call Marcus" "Follow ups" high
if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "Test task from Hermes tool"
    p = sys.argv[2] if len(sys.argv) > 2 else None
    imp = sys.argv[3] if len(sys.argv) > 3 else "medium"
    print(add_task_to_prime(t, p, imp))
