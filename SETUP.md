# Setup

This guide prepares the project for local development on macOS.

## Requirements

- macOS
- Python 3.11 or newer
- `pip`
- Chromium installed through Playwright
- SQLite CLI, optional but useful

## Install

```bash
cd /Users/vinod/Projects/visitor-parking-bot

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium

cp .env.example .env
```

## Environment Variables

The app reads `.env` from the project root.

```env
DATABASE_URL=sqlite:///./visitor_parking.db
SCREENSHOT_DIR=./screenshots

REGISTER2PARK_URL=https://www.register2park.com/
REGISTER2PARK_PROPERTY_NAME=Lakeside Urban Center Apartments

PLAYWRIGHT_HEADLESS=false
PLAYWRIGHT_TIMEOUT_MS=30000
MANUAL_CAPTCHA_TIMEOUT_SECONDS=300

SCHEDULER_INTERVAL_SECONDS=7200
RETRY_DELAY_MINUTES=30

LOG_LEVEL=INFO
```

Important values:

- `PLAYWRIGHT_HEADLESS=false`: keeps Chromium visible so you can watch and solve CAPTCHA manually.
- `MANUAL_CAPTCHA_TIMEOUT_SECONDS=300`: waits up to 5 minutes for manual CAPTCHA completion.
- `SCHEDULER_INTERVAL_SECONDS=7200`: checks due registrations every 2 hours.
- `RETRY_DELAY_MINUTES=30`: retry delay after normal automation failure.

Do not commit `.env`; it is gitignored.

## Verify Setup

```bash
source .venv/bin/activate
pytest
```

Expected result:

```text
7 passed
```

## First Run

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## If Port 8000 Is Busy

Use another port:

```bash
uvicorn app.main:app --reload --port 8001
```

Or stop the old server with `Ctrl+C` in the terminal where it is running.
