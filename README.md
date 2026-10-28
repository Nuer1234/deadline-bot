# Discord Deadline Reminder Bot

A Discord bot that helps a study group keep track of homework and due dates. Add an
assignment with a short chat command and the bot reminds everyone each morning, one day
before it is due.

```
!add เขียนรายงาน Calculus 5/9 #calculus
!add Write physics lab report tomorrow
!list
!done 3
```

Built for a Thai study group, so the date parser understands everyday Thai expressions
(`พรุ่งนี้` = tomorrow, `ศุกร์` = Friday, `5 ก.ย.` = 5 September) alongside English and
numeric formats. All replies are in Thai because that is what the users speak.

## Commands

| Command | What it does |
|---|---|
| `!add <task> <date> [time] [#subject]` | Add a task with a due date |
| `!list` | Your unfinished tasks, soonest deadline first |
| `!list all` / `!list @friend` / `!list #calculus` | Whole server / someone else's / filtered by subject |
| `!done <id>` | Close a task (leaves the list but still counts in stats) |
| `!undone <id>` / `!del <id>` | Put it back / delete permanently |
| `!stats` / `!stats all` | Completion percentage and how many were submitted on time |
| `!setchannel #channel` | Set the channel for the daily reminder (admins only) |
| `!help` | Summary of every command |

**Accepted date formats** — `วันนี้` (today), `พรุ่งนี้` (tomorrow), `มะรืน` (day after
tomorrow), `ศุกร์` (next Friday), `5/9`, `5/9/2569` (Buddhist year), `5/9/69`,
`2026-09-05`, `5 ก.ย.`, `5 sep`. A time can follow the date, e.g. `5/9 16:30`. With no
time given, the deadline is 23:59 that day.

**Reminders** — every day at 08:00 (configurable) the bot posts a digest split into
overdue / due today / due tomorrow in the configured channel, mentioning each task owner.
Overdue tasks are re-posted every day until someone runs `!done`.

## Getting started

### 1. Create the bot on Discord

1. Open the [Discord Developer Portal](https://discord.com/developers/applications) → **New Application**
2. **Bot** tab → **Reset Token** → copy the token (it is shown only once)
3. On the same page, turn on **MESSAGE CONTENT INTENT** ⚠️ without it the bot cannot read
   messages and will never answer a command
4. **OAuth2 → URL Generator** → tick `bot`, then the permissions
   `Send Messages`, `Read Message History`, `Embed Links`, `Mention Everyone`
5. Open the generated link to invite the bot to your own test server

### 2. Install

**Create a virtual environment** — an isolated box for this project's libraries so they do
not mix with the system-wide Python. Other projects can then depend on a different
`discord.py` version without conflict, and uninstalling means deleting the `.venv` folder.

```powershell
git clone https://github.com/Nuer1234/deadline-bot.git
cd deadline-bot
python -m venv .venv
```

**Activate it** — the command depends on your terminal

| Terminal | Command |
|---|---|
| PowerShell (default on Windows 11) | `.\.venv\Scripts\Activate.ps1` |
| Command Prompt (cmd.exe) | `.venv\Scripts\activate.bat` |
| Git Bash / WSL | `source .venv/Scripts/activate` |
| macOS / Linux | `source .venv/bin/activate` |

If PowerShell says `running scripts is disabled on this system`, run this first. It only
affects that one window and changes nothing permanently.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Once active, the prompt is prefixed with `(.venv)`. **Every new terminal needs activating
again.** To skip that, call the venv's Python directly — the result is identical.

```powershell
.\.venv\Scripts\python.exe bot.py
```

**Install the libraries**

```powershell
pip install -r requirements.txt
```

`requirements.txt` has three entries: `discord.py` (talks to the Discord API),
`python-dotenv` (reads the `.env` file) and `tzdata` (the timezone database, which Windows
does not ship).

### 3. Put the token in .env

```powershell
Copy-Item .env.example .env
notepad .env
```

Set `DISCORD_TOKEN=` to the token from step 1 — paste it straight after the `=` with no
quotes and no surrounding spaces. Everything else is optional and falls back to a default.

| Variable | Default | What it does |
|---|---|---|
| `DISCORD_TOKEN` | *(required)* | The bot's token |
| `COMMAND_PREFIX` | `!` | Change to `?` or `.` if it clashes with another bot on the server |
| `DATA_FILE` | `data.json` | Where tasks are stored |
| `REMINDER_HOUR` | `8` | Hour (Thai time) to post the daily digest |
| `REMINDER_LEAD_DAYS` | `1` | How many days ahead to warn |
| `CHECK_INTERVAL_MINUTES` | `15` | How often the bot wakes up to check whether the digest is due |

⚠️ `.env` is already listed in `.gitignore`. **Never commit it and never send it to
anyone** — whoever holds the token controls the bot. If it leaks, press **Reset Token** in
the Developer Portal and the old one dies immediately.

### 4. Run it

```powershell
python bot.py
```

If everything is set up you will see a log like this and the bot appears online:

```
2026-08-30 17:30:21 INFO    discord.client: logging in using static token
2026-08-30 17:30:23 INFO    discord.gateway: Shard ID None has connected to Gateway
2026-08-30 17:30:23 INFO    deadline-bot: logged in as DeadlineBot#1234 (1 guild)
```

- The warning `PyNaCl is not installed, voice will NOT be supported` is harmless — it is
  about voice features this bot does not use
- Stop the bot with **Ctrl+C**
- **Closing the terminal takes the bot offline**, because it runs on your machine. See
  step 7 for keeping it up.

### 5. First-time setup in the server

Type this in the channel where reminders should go. Once per server — the choice is
remembered in `data.json`.

```
!setchannel
!add ทดสอบระบบเตือน พรุ่งนี้
!list
```

### 6. Test the reminder without waiting until tomorrow morning

Normally the digest goes out once a day at 08:00. To see it now, set this in `.env`:

```
REMINDER_HOUR=0
CHECK_INTERVAL_MINUTES=1
```

Then delete `data.json` (or set `last_digest_date` inside it to `null`), because the bot
remembers that today's digest was already sent and will not repeat it. Restart, run
`!setchannel`, add a task due tomorrow, and wait at most a minute for the reminder to
appear. **Change the values back when you are done.**

### 7. Keeping the bot online 24/7

- **Classroom demo** — running locally is fine, just leave the terminal open
- **Real use by friends** — deploy it, e.g. on Railway: push to GitHub (`.env` stays
  behind thanks to `.gitignore`) → create a project from the repo → under **Variables**
  add `DISCORD_TOKEN` as an environment variable → Railway reads the `Procfile` and runs
  `python bot.py`
- Caveat: on Railway `data.json` is wiped on every redeploy unless a volume is attached —
  another reason to move to SQLite with a persistent volume in a future version

### 8. Tests and offline preview

```powershell
python -m unittest discover -s tests
python demo.py
```

`demo.py` simulates adding tasks and prints `!list` output and a sample reminder in the
terminal. It is very handy while working on the date parser, since there is no need to
restart the real bot every time.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `'python' is not recognized` | Python is not installed, or it was installed without ticking *Add python.exe to PATH* — reinstall and tick that box |
| `Activate.ps1 cannot be loaded ... running scripts is disabled` | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` before activating |
| `ModuleNotFoundError: No module named 'discord'` | The venv is not active (no `(.venv)` in the prompt), or the libraries went to a different Python — activate, then `pip install -r requirements.txt` again |
| `SystemExit: DISCORD_TOKEN is not set` | `.env` does not exist yet, or the variable name is misspelled (it must be exactly `DISCORD_TOKEN`) |
| `discord.errors.LoginFailure: Improper token has been passed` | Wrong token, a stray space, or it was reset — copy the whole line again |
| `PrivilegedIntentsRequired` on startup | **MESSAGE CONTENT INTENT** is still off in the Developer Portal's Bot page |
| Bot shows online but ignores commands | Usually the intent is off · or the bot lacks *Send Messages / Read Message History* in that channel (Edit Channel → Permissions) · or the prefix is wrong |
| Commands work but no morning digest | `!setchannel` was never run · or the bot was down at that hour (it catches up as soon as it is back online) |
| `ZoneInfoNotFoundError: 'Asia/Bangkok'` | `tzdata` is missing — `pip install tzdata` (the code has a UTC+7 fallback, but installing it is more correct) |
| Thai text or emoji look garbled in `demo.py` | The console is using cp874 — the code calls `reconfigure(encoding="utf-8")`, and if it still breaks, run `chcp 65001` first |
| Want to wipe everything and start over | Stop the bot, delete `data.json`, restart (task ids restart from 1) |

## Code layout

```
bot.py          Discord commands + the reminder loop (the only module that imports discord)
dateparse.py    Human date text -> timezone-aware datetime
storage.py      Reads/writes the JSON store (isolated so it can become SQLite later)
reminders.py    Decides which tasks to remind about today
formatting.py   Thai date and message formatting
demo.py         Prints real output without connecting to Discord
tests/          33 unittest cases covering date parsing, storage and reminders
```

All logic deliberately lives outside `bot.py`, so the tests need no token, no network
connection and no mocking of the Discord API.

## Problems hit along the way, and how they were solved

**1. Timezones** — the first version just called `datetime.now()`. Deployed to a free host
set to UTC, anything due at midnight was off by seven hours. Fixed by forcing every
datetime in the system to be timezone-aware and bound to Asia/Bangkok, and by storing
ISO 8601 with the offset attached (`2026-09-05T23:59:00+07:00`).

**2. Windows has no timezone database** — `ZoneInfo("Asia/Bangkok")` crashes on Windows
because there is no system tzdata. Fixed by adding `tzdata` to the requirements *and*
writing a fixed UTC+7 fallback (Thailand has never used DST, so the two always agree),
which makes the code runnable on any machine as-is.

**3. "Days remaining" means something different to a human and a computer** — dividing a
`timedelta` by 86400 made a task due at 23:59 tomorrow read as "1 day left" in the morning
and "0 days left" late at night. Fixed by subtracting at the `date` level instead, so it
counts calendar days the way people do.

**4. Duplicate reminders after a restart** — checking only "is anything due tomorrow?"
meant every restart fired the digest again. Fixed by recording the dates a task was
already announced on (`reminded_on`). The opposite problem also existed: if the bot was
down at exactly 08:00, that day's reminder was lost forever. So the loop asks "has today's
digest gone out yet?" instead of firing precisely at 08:00 — come back at 2pm and it still
sends the one for today.

**5. Data loss if the process dies mid-write** — overwriting the JSON in place and getting
killed halfway corrupts the whole file. Fixed by writing to a temporary file and then
calling `os.replace()`, which is atomic. If a corrupt file is found at startup it is
renamed to `.broken` rather than preventing the bot from starting.

## Roadmap

- [ ] Move from JSON to SQLite (only `storage.py` needs to change)
- [ ] Switch to slash commands (`/add`) for autocomplete
- [ ] Per-user reminder times and multiple warnings (3 days + 1 day)
- [ ] Deploy to Railway for 24/7 uptime

## License

MIT — see [LICENSE](LICENSE).
