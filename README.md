# sydney_social_bot

Daily bot: scans a tracked list of Sydney young-adult social/sport/party
Instagram accounts for new event posts, extracts the details (where, when,
cost, who), and messages them to a Telegram chat. Also runs a slow, rotating
account-discovery sweep and queues candidates for your approval.

The account list in `config/accounts.yaml` (122 accounts as of writing) was
built by hand — see the project this came from for how. This repo is just
the automation on top of it.

## How it works

```
main.py (run once daily by cron)
  ├─ src/scan.py       for each account in config/accounts.yaml:
  │                       vb go <profile> → read post grid → diff against
  │                       state.json → for anything new: screenshot + read
  │                       caption → src/extract.py (Anthropic vision call)
  │                       → src/notify.py (Telegram)
  └─ src/discover.py   IG-search sweep + collab-tag mining (see
                        config/discovery.yaml) → new handles → append to
                        config/candidates.yaml → one Telegram summary
```

Candidates are **never** auto-added to the tracked list. Review
`config/candidates.yaml` (or the Telegram message) and run:

```
python approve.py <handle> [<handle> ...]   # move candidate(s) into accounts.yaml
python approve.py --list                    # see what's pending
python approve.py --reject <handle> ...     # drop a candidate
```

## Prerequisite: a logged-in Instagram session for vibatchium

This bot assumes `vb --session instagram ...` already works and is already
logged into an Instagram account — it never does the login itself (IG's
login flow expects a human, and often 2FA).

If you already have vibatchium logged into Instagram on this server under
session name `instagram`, skip this section.

**If not**, the easiest path is usually: log in once somewhere with a
display (your laptop), then carry the cookies over —

```bash
# On a machine with a screen:
vb session new instagram
vb --session instagram start          # headless=false at a TTY, pops a window
vb --session instagram go https://www.instagram.com/accounts/login/
# ... log in by hand in the window that opens ...
vb --session instagram stop

# Copy the profile directory to the server:
rsync -av ~/.config/vibatchium/profiles/instagram/ user@server:~/.config/vibatchium/profiles/instagram/
```

On the server, `vb --session instagram start --headless` (or just
`vb --session instagram go <url>` — it auto-starts) will now reuse those
cookies with no display needed. Keep the vibatchium daemon running
persistently (it auto-spawns on first `vb` call and stays up); this bot
doesn't manage that lifecycle.

If `VIBATCHIUM_SESSION` isn't `instagram` on your box, set `VB_SESSION` in
`.env` to match.

## Setup

```bash
cd sydney_social_bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — see below.
- `ANTHROPIC_API_KEY` — used to read event details out of flyer
  screenshots. Without it, the bot still detects new posts but can't
  extract structured fields (logs a warning, skips the Telegram send for
  that post).
- `VB_BIN` / `VB_SESSION` — only change if your vibatchium binary or
  session name differs from `vb` / `instagram`.

### Telegram bot setup

1. In Telegram, message **@BotFather** → `/newbot` → follow the prompts →
   you'll get a token that looks like `123456789:AAExampleTokenHere`. Put
   that in `TELEGRAM_BOT_TOKEN`.
2. Start a chat with your new bot (search its @username, hit Start), or
   add it to a group you want events posted in.
3. Get the chat ID: send any message to the bot/group, then visit
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser —
   look for `"chat":{"id": ...}` in the JSON. For a group chat this is
   usually a negative number. Put that in `TELEGRAM_CHAT_ID`.
4. Send a test message to confirm:
   ```bash
   .venv/bin/python -c "from src import notify; notify.send_message('test 🎉')"
   ```

### Cron

```bash
mkdir -p logs
crontab -e
```

Paste (adjusted for your actual path — see `setup/crontab.example`):

```
0 9 * * * cd /path/to/sydney_social_bot && /path/to/sydney_social_bot/.venv/bin/python main.py >> logs/run.log 2>&1
```

## First run

The first run **baselines** every tracked account (records its current
newest post) instead of reporting all 122 accounts' entire recent history
into your chat at once. You'll start seeing real notifications from the
second run onward, for anything genuinely posted after the first run.

Run it manually once to baseline immediately, rather than waiting for
tomorrow's cron:

```bash
.venv/bin/python main.py
```

## Notes / caveats

- **This is meaningful automated traffic on the logged-in account.**
  Scanning ~120 profiles + running search queries + tagged-tab scrolling
  daily is real usage. Watch `vb logs --since 1h | grep walled` after the
  first few runs to make sure Instagram isn't challenging the session. If
  it does, consider raising `SCAN_DELAY_SECONDS` or lowering
  `DISCOVERY_QUERIES_PER_RUN` / `DISCOVERY_HUBS_PER_RUN` in `.env`.
- **Post captions and flyer images are untrusted content.** Anyone posting
  to a public account on the tracked list can put arbitrary text in a
  caption. `src/extract.py`'s system prompt explicitly tells the model to
  treat post content as data, not instructions, and the extraction call
  can only return a fixed set of fields via forced tool-use — it has no
  other tool access and can't take further action.
- **Discovery is deliberately slow.** `config/discovery.yaml` has ~70
  search queries and 10 hub accounts; each run only burns through a
  rotating slice (`DISCOVERY_QUERIES_PER_RUN` / `DISCOVERY_HUBS_PER_RUN`
  per day) so the full sweep takes roughly a week to cycle through rather
  than hitting IG with everything at once.
- **Near-duplicate accounts.** Several tracked accounts in
  `config/accounts.yaml` are flagged in their `note` field as
  near-duplicates of another handle (e.g. multiple "Inner West Run Club"
  accounts). Worth pruning the dead ones once you see which actually post.
- State (`state.json`) and `.env` are gitignored — don't lose `state.json`
  on this repo alone, back it up if you care about not re-baselining.
