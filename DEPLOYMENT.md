# Deployment And Running Locally

This project is designed as a local-only automation tool. The recommended
deployment is a local FastAPI process on your Mac.

## Local Development Server

```bash
cd /Users/vinod/Projects/visitor-parking-bot
source .venv/bin/activate
uvicorn app.main:app --reload
```

Routes:

- UI: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

`--reload` watches source files and reloads after code changes.

## Running Without Reload

Use this for a more stable local session:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Scheduler

The scheduler starts automatically during FastAPI startup and stops during
shutdown. You do not need to run a separate scheduler process.

Default behavior:

- Checks every `SCHEDULER_INTERVAL_SECONDS`.
- Processes registrations with status `PENDING` or `ACTIVE`.
- Runs an attempt when `next_registration_at <= now`.
- Skips `COMPLETED`, `FAILED`, and `CANCELLED`.

## Browser Behavior

Chromium launches through Playwright.

- Headed mode is the default.
- Keep the browser open while the automation runs.
- If CAPTCHA appears, solve it manually in that browser.
- The automation resumes after CAPTCHA is solved or after registration content appears.

## Local Persistence

The default database is:

```text
/Users/vinod/Projects/visitor-parking-bot/visitor_parking.db
```

Open the DB from the project root:

```bash
cd /Users/vinod/Projects/visitor-parking-bot
sqlite3 visitor_parking.db
```

If you run `sqlite3 visitor_parking.db` from `~`, you will open or create
`~/visitor_parking.db`, which is not the project database.

## Not Recommended For Public Hosting

Do not expose this app to the public internet without adding:

- Authentication
- HTTPS
- Secrets management
- Access controls
- Proper database migrations
- Operational monitoring

The current app is built for one local user on one trusted machine.
