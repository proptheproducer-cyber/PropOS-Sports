"""
add_task_to_prime tool for Hermes Agent.

Files a task Prop mentions into PROP PRIME (prime2.json) via the local
cartella-ingest service. Structured exactly like send_message_tool.py:
a SCHEMA dict (name/description/parameters) + a synchronous handler taking a
single `args` dict + registry.register() at the bottom.

Env (set on the hermes-gateway service):
    CARTELLA_TOKEN         same secret as cartella-ingest.service
    CARTELLA_INGEST_URL    default http://127.0.0.1:8787/prime/ingest

Install: drop this file in /usr/local/lib/hermes-agent/tools/ (same dir as
send_message_tool.py) so the registry autoloads it, then restart hermes-gateway.
"""
import os
import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

INGEST_URL = os.environ.get("CARTELLA_INGEST_URL", "http://127.0.0.1:8787/prime/ingest")
INGEST_TOKEN = os.environ.get("CARTELLA_TOKEN", "")


ADD_TASK_TO_PRIME_SCHEMA = {
    "name": "add_task_to_prime",
    "description": (
        "File a task Prop needs to do into PROP PRIME (the brain, prime2.json).\n\n"
        "Call this whenever Prop mentions an action item, follow-up, commitment, "
        "reminder, or appointment in ANY channel (voice, text, Telegram, DM). "
        "Log it the same day. When unsure whether something is a task, log it. "
        "The task lands in the app's approval card for Prop to confirm."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "The action item in imperative phrasing, e.g. "
                               "'Follow up with Marcus Wright about the partnership'.",
            },
            "project": {
                "type": "string",
                "description": "Existing section to file it under, e.g. 'Follow ups' "
                               "for a follow-up. Omit if unsure — it goes to Inbox.",
            },
            "importance": {
                "type": "string",
                "enum": ["low", "medium", "high", "urgent"],
                "description": "Urgency / client value. Sets pomodoro slots "
                               "(low=1, medium=2, high=3, urgent=4).",
            },
        },
        "required": ["task"],
    },
}


def add_task_to_prime_tool(args, **kw):
    """Handle add_task_to_prime tool calls: POST the task to cartella-ingest."""
    task = (args.get("task") or "").strip()
    if not task:
        return {"error": "No task text provided."}

    payload = {"task": task, "importance": args.get("importance") or "medium"}
    project = args.get("project")
    if project:
        payload["project"] = project

    req = urllib.request.Request(
        INGEST_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "X-Cartella-Token": INGEST_TOKEN},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        return {"error": "PRIME ingest error (%s): %s" % (e.code, detail)}
    except Exception as e:
        logger.warning("add_task_to_prime: ingest unreachable: %s", e)
        return {"error": "Couldn't reach PRIME ingest: %s" % e}

    if data.get("ok") and data.get("added"):
        a = data["added"][0]
        return {
            "success": True,
            "platform": "prime",
            "project": a.get("project"),
            "task": a.get("task"),
            "id": a.get("id"),
            "message": "✅ Logged: %s → %s" % (a.get("task"), a.get("project")),
        }
    return {"error": "Nothing filed: %s" % data.get("error", "unknown error")}


# --- Registry ---
from tools.registry import registry

registry.register(
    name="add_task_to_prime",
    toolset="productivity",
    schema=ADD_TASK_TO_PRIME_SCHEMA,
    handler=add_task_to_prime_tool,
    emoji="\U0001f9e0",
)
