# Cartella → PROP PRIME ingest

Gives the Cartella agent a safe way to write a recognized task into the brain
(`/var/www/prop/prime2.json`). Cartella understands you on Telegram; this
endpoint files the task into the right project as a **pending** item, and the
app shows it in the yellow "Added by Cartella — needs your approval" card.

It only edits the JSON file. Pomodoro, galaxy view, and the app's save/render
logic are untouched.

## What it does with a request

`POST /prime/ingest` with header `X-Cartella-Token: <secret>` and a JSON body:

```json
{ "task": "Follow up with Marcus Wright", "project": "Follow ups", "importance": "high" }
```

- Matches `project` to an existing project by name (case-insensitive, fuzzy).
  If none matches it creates the project; if `project` is omitted the task goes
  to an auto-created **Inbox**.
- Appends the task to that project's `tasks[]` as `pending:true`, `added:"Cartella"`.
- `importance` (low/medium/high/urgent) sets pomodoro slots when `pomos` is not given.
- Batch form: `{ "tasks": [ {…}, {…} ] }`.

Response: `{"ok":true,"added":[{"project":"Follow ups","task":"…","id":"…"}]}`

## Deploy on the VPS (run as root in Termius)

```bash
# 1) install the service file (single curl, same as prime2.html)
curl -fsSL -o /var/www/prop/cartella_ingest.py \
  "https://raw.githubusercontent.com/proptheproducer-cyber/PropOS-Sports/claude/prime2-deploy-gqllbi/cartella/cartella_ingest.py"

# 2) create the systemd unit with YOUR secret (change the token!)
SECRET="$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9')"
curl -fsSL "https://raw.githubusercontent.com/proptheproducer-cyber/PropOS-Sports/claude/prime2-deploy-gqllbi/cartella/cartella-ingest.service" \
  | sed "s/CHANGE_ME_TO_A_LONG_RANDOM_STRING/$SECRET/" > /etc/systemd/system/cartella-ingest.service
echo "YOUR CARTELLA TOKEN (save this for Cartella): $SECRET"

# 3) make sure the file is owned by www-data so the service can write it
chown www-data:www-data /var/www/prop/prime2.json

# 4) start it
systemctl daemon-reload
systemctl enable --now cartella-ingest
systemctl status cartella-ingest --no-pager | head -5
```

### Expose it through nginx

Add this inside the same `server { … }` block that serves the app, then reload:

```nginx
location = /prime/ingest {
    proxy_pass http://127.0.0.1:8787;
    proxy_set_header Host $host;
}
```

```bash
nginx -t && systemctl reload nginx
```

### Test it

```bash
curl -s -X POST http://165.227.197.92/prime/ingest \
  -H "X-Cartella-Token: <YOUR_SECRET>" \
  -d '{"task":"Follow up with Marcus Wright","project":"Follow ups","importance":"high"}'
# -> {"ok":true,"added":[{"project":"Follow ups","task":"Follow up with Marcus Wright",...}]}
```

Reload the app → Board → the task is waiting in the approval card.

## Wire it into Cartella

Give Cartella a tool/action it can call. Contract:

- **Method/URL:** `POST http://165.227.197.92/prime/ingest`
  (use an `https://your-domain` URL once you have one — plain HTTP sends the
  token in the clear)
- **Headers:** `X-Cartella-Token: <YOUR_SECRET>`, `Content-Type: application/json`
- **Body:** `{ "task": "<what to do>", "project": "<existing section name>", "importance": "low|medium|high|urgent" }`

Add to Cartella's system prompt, roughly:

> You have a tool `add_task_to_prime`. Whenever the user mentions something they
> need to do — a follow-up, reminder, appointment, or action item — call it to
> file the task into PROP PRIME. Choose `project` from the user's existing
> sections (e.g. "Follow ups"); if unsure, omit it. Judge `importance` from
> urgency and client value. Confirm back to the user what you filed and where.

Tool schema (JSON-schema style):

```json
{
  "name": "add_task_to_prime",
  "description": "File a task the user needs to do into PROP PRIME (the brain).",
  "input_schema": {
    "type": "object",
    "properties": {
      "task": { "type": "string", "description": "The action item, imperative phrasing" },
      "project": { "type": "string", "description": "Existing section name, e.g. 'Follow ups'" },
      "importance": { "type": "string", "enum": ["low", "medium", "high", "urgent"] }
    },
    "required": ["task"]
  }
}
```

Security notes: keep the token secret; anyone with the URL + token can add
tasks. Move to HTTPS (a domain + Let's Encrypt) before relying on it heavily.
