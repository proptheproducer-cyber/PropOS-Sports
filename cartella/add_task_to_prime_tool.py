"""
add_task_to_prime tool for Hermes Agent.

Files a task Prop mentions into PROP PRIME (prime2.json) via the local
cartella-ingest service. Structured like send_message_tool.py: a SCHEMA dict +
an async handler + registry.register() at the bottom.

Env (set on the hermes-gateway service):
    CARTELLA_TOKEN         same secret as cartella-ingest.service
    CARTELLA_INGEST_URL    default http://127.0.0.1:8787/prime/ingest

Install: drop this file in /usr/local/lib/hermes-agent/tools/ (same dir as
send_message_tool.py) so the registry autoloads it, then restart hermes-gateway.

NOTE: the SCHEMA shape and handler signature below mirror the conventions
visible in send_message_tool.py; confirm against SEND_MESSAGE_SCHEMA and the
send_message_tool() signature and adjust if your registry differs.
"""
import os
import json

try:
    import aiohttp
except ImportError:  # pragma: no cover
    aiohttp = None

INGEST_URL = os.environ.get("CARTELLA_INGEST_URL", "http://127.0.0.1:8787/prime/ingest")
INGEST_TOKEN = os.environ.get("CARTELLA_TOKEN", "")


ADD_TASK_TO_PRIME_SCHEMA = {
    "name": "add_task_to_prime",
    "description": (
        "File a task Prop needs to do into PROP PRIME (the brain, prime2.json). "
        "Call this whenever Prop mentions an action item, follow-up, commitment, "
        "reminder, or appointment in ANY channel (voice, text, Telegram, DM). "
        "Log it the same day. It lands in the app's approval card for Prop to confirm."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "The action item in imperative phrasing, "
                               "e.g. 'Follow up with Marcus Wright about the partnership'.",
            },
            "project": {
                "type": "string",
                "description": "Existing section to file it under, e.g. 'Follow ups'. "
                               "Omit if unsure — it will go to Inbox.",
            },
            "importance": {
                "type": "string",
                "enum": ["low", "medium", "high", "urgent"],
                "description": "Urgency / client value. Sets pomodoro slots.",
            },
        },
        "required": ["task"],
    },
}


async def add_task_to_prime_tool(task, project=None, importance="medium", **kwargs):
    """Handler: POST the task to the local cartella-ingest endpoint."""
    if aiohttp is None:
        return {"error": "aiohttp not installed. Run: pip install aiohttp"}

    task = (task or "").strip()
    if not task:
        return tool_error("No task text provided.")

    payload = {"task": task, "importance": importance or "medium"}
    if project:
        payload["project"] = project

    headers = {"Content-Type": "application/json", "X-Cartella-Token": INGEST_TOKEN}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(INGEST_URL, headers=headers, json=payload) as resp:
                body = await resp.text()
                if resp.status != 200:
                    return tool_error("PRIME ingest error (%s): %s" % (resp.status, body))
                data = json.loads(body)
    except Exception as e:
        return tool_error("Couldn't reach PRIME ingest: %s" % e)

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
    return tool_error("Nothing filed: %s" % data.get("error", "unknown error"))


# --- Registry ---
from tools.registry import registry, tool_error

registry.register(
    name="add_task_to_prime",
    toolset="productivity",
    schema=ADD_TASK_TO_PRIME_SCHEMA,
    handler=add_task_to_prime_tool,
    emoji="🧠",
)
