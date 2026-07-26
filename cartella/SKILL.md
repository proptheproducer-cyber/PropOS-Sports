---
name: prop-prime-task-logging
description: "Reliable task/follow-up logging into PROP PRIME (prime2.json) via the add_task_to_prime tool — same-day, one source of truth, no hand-editing of JSON."
version: 1.0.0
author: Prop + Hermes
tags: [tasks, follow-ups, logging, prime2, cartella, reminders]
related_skills: [prop-daily-briefing, vps-deployment]
---

# PROP PRIME Task Logging (add_task_to_prime)

The canonical way to log a task, follow-up, or commitment into PROP PRIME. Use
the `add_task_to_prime` tool — do **not** hand-edit `prime2.json`. The tool
writes the file safely (atomic, locked, correct shape) and the app shows the
task in the yellow "Added by Cartella — needs your approval" card.

This supersedes the "hand-write prime2.json" step in `prop-daily-briefing`. The
timing and briefing rules there still apply; only the *mechanism* changes.

## When to call

**Trigger:** Prop mentions something to do — a task, follow-up, commitment, or
reminder — in ANY channel (voice, text, Telegram, DM). Log it the **same day**.

When unsure whether it's a task → log it (over-capture is fine; approval catches
noise).

## The tool

```
name: add_task_to_prime
description: File a task Prop needs to do into PROP PRIME (the brain).
parameters:
  task        (string, required)  The action item, imperative phrasing.
                                   e.g. "Follow up with Marcus Wright about strategic partnership"
  project     (string, optional)  Existing section name. Follow-ups -> "Follow ups".
                                   Omit if unsure -> lands in "Inbox".
  importance  (string, optional)  low | medium | high | urgent  (sets pomodoro slots)
returns: one-line confirmation string to relay to Prop.
```

**Project routing:** a follow-up/waiting-on-reply/business contact → `"Follow ups"`
(planet business). Otherwise pass the most fitting existing project name; the
endpoint fuzzy-matches and creates it if missing.

**Confirmation:** relay the tool's result to Prop in one line, e.g.
`✅ Logged: Follow up with Marcus Wright`.

## What the tool writes (prime2.json task format)

The endpoint produces exactly this shape (matches prop-daily-briefing §Task Format):

```json
{
  "id": "auto-generated",
  "name": "Follow up with Marcus Wright about strategic partnership",
  "pomos": 3,
  "len": 30,
  "done": 0,
  "complete": false,
  "pending": true,
  "source": "cartella",
  "added": "2026-07-26"
}
```

- `pomos` default **2** (importance high → 3, urgent → 4, low → 1); `len` default **30**.
- `pending: true` → waits in the approval card until Prop approves in the app.
- `source: "cartella"`, `added` = today (YYYY-MM-DD).

## How it connects

`add_task_to_prime` POSTs to the local ingest service on the same VPS:

- `POST http://127.0.0.1:8787/prime/ingest`
- header `X-Cartella-Token: <secret>` (same secret as the cartella-ingest service)
- body `{"task": "...", "project": "...", "importance": "..."}`

Handler: `hermes_tool_add_task.py` → `add_task_to_prime(task, project, importance)`.

Required environment on `hermes-gateway` (systemd):

```
Environment=CARTELLA_TOKEN=<same secret as cartella-ingest.service>
Environment=CARTELLA_INGEST_URL=http://127.0.0.1:8787/prime/ingest
```

## Failure handling

If the tool returns an error (service down, bad token), tell Prop plainly:
"Couldn't log that to PRIME right now" — and keep the task in Hermes's own list
so it still appears in the next morning brief (per prop-daily-briefing: Hermes's
list is source of truth if sync fails). Retry the log when the service is back.
