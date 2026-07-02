# visitor-parking-bot

Local visitor parking registration automation for Register2Park-style flows.

This project runs a FastAPI app with a browser UI, SQLite persistence,
APScheduler-based retries, and Playwright browser automation. It can run
locally on macOS or as a single-server AWS Lightsail deployment. It is intended
for legitimate visitor parking registration only, on registrations you are
allowed to submit.

## What It Does

- Serves a registration form locally or through an AWS/Nginx public endpoint.
- Saves vehicle registration requests to SQLite.
- Immediately starts the first Playwright registration attempt after submit.
- Uses the actual first successful registration time as the daily schedule anchor.
- Re-registers every 24 hours until the requested number of successful days is reached.
- Stores every attempt with status, message, screenshot path, and confirmation text.
- Pauses for manual CAPTCHA completion in the visible browser, then resumes from the same page.
- Stops safely on login, OTP, payment, or other security/approval gates.
- Deletes local debug screenshots after 24 hours by default.

## Safety Rules

This bot does not bypass security mechanisms.

- CAPTCHA: pauses and waits for you to solve it manually in the headed browser.
- OTP, login, payment, or security walls: stops and records the attempt.
- Screenshots stay on the machine/server running the app.
- Personal data is not hardcoded; registration details come from the UI/API request.
- This is a single-user automation service, not a multi-tenant SaaS app.

## Documentation

- [SETUP.md](SETUP.md): install Python dependencies, Playwright, and `.env`.
- [DEPLOYMENT.md](DEPLOYMENT.md): run locally, ports, VS Code/macOS notes, and service guidance.
- [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md): complete beginner-friendly AWS Lightsail deployment guide.
- [API.md](API.md): endpoints, request payloads, statuses, and examples.
- [AUTOMATION.md](AUTOMATION.md): Register2Park Playwright flow, CAPTCHA pause/resume, selector notes.
- [DATABASE.md](DATABASE.md): SQLite tables, useful queries, and where data is stored.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md): common errors and how to fix them.
- [PROJECT_NOTES.md](PROJECT_NOTES.md): issues faced, fixes implemented, limitations, and future work.

## Quick Start

```bash
cd /Users/vinod/Projects/visitor-parking-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

Interactive API docs:

```text
http://127.0.0.1:8000/docs
```

## Project Structure

```text
visitor-parking-bot/
  README.md
  SETUP.md
  DEPLOYMENT.md
  AWS_DEPLOYMENT.md
  API.md
  AUTOMATION.md
  DATABASE.md
  TROUBLESHOOTING.md
  PROJECT_NOTES.md
  requirements.txt
  .env.example
  app/
    main.py                       # FastAPI app, local UI, API routes
    config.py                     # .env-backed settings
    database.py                   # SQLAlchemy engine/session/table setup
    models.py                     # registrations and registration_attempts
    schemas.py                    # API validation and response models
    scheduler.py                  # APScheduler loop
    automation/
      register2park_bot.py        # Playwright Register2Park automation
    services/
      registration_service.py     # scheduling/business logic
      runtime_status.py           # in-memory live automation status for UI
    static/
      index.html                  # local form UI
    utils/
      logger.py
  screenshots/                    # local debug screenshots, cleaned after 24 hours by default
  tests/
    test_registration_service.py
  visitor_parking.db              # local SQLite DB, gitignored
```

## Core Lifecycle

1. User submits the local form or calls `POST /registrations`.
2. Backend validates required fields, plate confirmation, email, year, and days.
3. Registration is saved as `PENDING` with `next_registration_at = now`.
4. First Playwright attempt starts immediately in a FastAPI background task.
5. On success:
   - `first_registered_at` is set on the first success only.
   - `last_registered_at` is set to the actual success timestamp.
   - `expires_at = success timestamp + 24 hours`.
   - `next_registration_at = success timestamp + 24 hours`.
   - `registration_count` increments.
6. Scheduler checks due registrations every 2 hours by default.
7. Registration becomes `COMPLETED` when `registration_count >= days`.

## Run Tests

```bash
source .venv/bin/activate
pytest
```

The tests use in-memory SQLite and stub the browser call, so no network or
browser session is required.
