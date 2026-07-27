---
name: prop-prime-task-logging
description: "Capture tasks into PROP PRIME. Use WHENEVER Prop mentions something to do, a follow-up, a commitment, a reminder, an appointment, or a new project/initiative — in any channel (voice, text, Telegram, DM, screenshot). Recognize it and file it via the add_task_to_prime tool. Same-day, one source of truth."
version: 1.1.0
author: Prop + Hermes
tags: [tasks, follow-ups, logging, prime2, cartella, reminders, capture]
related_skills: [prop-daily-briefing, vps-deployment]
---

# PROP PRIME Task Capture (add_task_to_prime)

The canonical way to log anything Prop needs to do into PROP PRIME. Use the
`add_task_to_prime` tool — never hand-edit prime2.json. The tool writes the
brain safely and the task shows in the app's approval card.

This is the *mechanism* referenced by prop-daily-briefing's "Adding a Task"
step. Where that skill says "log to prime2.json," it means **call this tool**.

## Recognize a task — trigger phrases

Call `add_task_to_prime` when Prop says anything shaped like an action or
commitment, in any channel (including voice-to-text and screenshots). Examples:

- "I need to **follow up with Marcus Wright** about the partnership." → task
- "**Remind me to** send Jack the contract tomorrow." → task
- "**Don't let me forget** to renew the domain." → task
- "I **should** book the studio for Friday." → task
- "**Call / email / text / DM** <person> about <thing>." → task
- "We **have to** finish the deck before the pitch." → task
- "**Schedule / set up** a meeting with the CMC board." → task
- "I want to **start a project** for the Aaron Le album." → new project (see below)

When genuinely unsure whether it's a task → **log it anyway**. Over-capture is
fine; the approval card catches noise. Do NOT log pure venting, rhetorical
questions, already-completed statements ("I already emailed her"), or
hypotheticals ("maybe someday I'll…").

If one message contains several action items, call the tool **once per task**.

## Route it — pick the project

- A follow-up, a reply Prop owes someone, a waiting-on business contact →
  project **"Follow ups"**.
- Otherwise match to Prop's most fitting **existing** project (e.g. "Aaron Le
  Album", "ONUS PromptLab", "CMC").
- **New project/initiative:** if Prop describes a new area of work, pass that
  as the `project` name with the first concrete task — the tool auto-creates
  the project. (e.g. task "Brainstorm album concepts", project "Aaron Le Album".)
- If you can't tell → omit `project`; it lands in **Inbox** for Prop to sort.

Set `importance` from urgency and client value: low / medium / high / urgent.

## Call it

```
add_task_to_prime(
  task="Follow up with Marcus Wright about the partnership",
  project="Follow ups",
  importance="high"
)
```

Then **confirm to Prop in one line**, echoing where it went:
`✅ Logged: Follow up with Marcus Wright → Follow ups`

## What the tool writes (prime2.json task format)

```json
{
  "id": "auto",
  "name": "Follow up with Marcus Wright about the partnership",
  "pomos": 3,            // from importance: low=1, medium=2, high=3, urgent=4
  "len": 30,
  "done": 0,
  "complete": false,
  "pending": true,       // waits in the app's approval card
  "source": "cartella",
  "added": "YYYY-MM-DD"
}
```

## Connection (for reference)

`add_task_to_prime` POSTs to the local ingest service on this VPS:
`POST http://127.0.0.1:8787/prime/ingest`, header `X-Cartella-Token: <secret>`.
Env on hermes-gateway: `CARTELLA_TOKEN`, `CARTELLA_INGEST_URL`.

## Failure handling

If the tool returns an error, tell Prop plainly ("couldn't log that to PRIME
right now"), keep the item in your own list so it still appears in the next
6:30 AM brief, and retry when the service is back.
