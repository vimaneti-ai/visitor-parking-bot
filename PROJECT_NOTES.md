# Project Notes

This document records the main issues encountered while building and testing
the Visitor Parking Bot, the fixes implemented, and future improvements that
would make the project stronger.

## Issues Faced And Fixes Implemented

### Port 8000 Already In Use

Issue:

`uvicorn app.main:app --reload` failed with:

```text
ERROR: [Errno 48] Address already in use
```

Cause:

Another uvicorn process was already running on port `8000`.

Fix:

- Stopped the previous server process.
- Documented how to use a different port with `--port 8001`.
- Added troubleshooting guidance in [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

### Wrong SQLite Database Opened

Issue:

Running `sqlite3 visitor_parking.db` from the home directory opened an empty DB
with no `registrations` table.

Cause:

SQLite opened `~/visitor_parking.db` instead of the project DB.

Fix:

- Documented the correct DB path:

```text
/Users/vinod/Projects/visitor-parking-bot/visitor_parking.db
```

- Added database inspection commands in [DATABASE.md](DATABASE.md).

### AWS Production SQLite Needed `sudo`

Issue:

On AWS, opening:

```bash
sqlite3 /opt/visitor-parking-bot/data/visitor_parking.db
```

failed with:

```text
unable to open database file
```

Cause:

The production DB folder is owned by the `visitorbot` service user.

Fix:

- Used `sudo sqlite3 /opt/visitor-parking-bot/data/visitor_parking.db`.
- Documented production DB inspection in [DATABASE.md](DATABASE.md).
- Added troubleshooting guidance in [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

### AWS SSH Key Was Missing On Mac

Issue:

SSH from Mac failed with:

```text
Permission denied (publickey)
```

Cause:

The Lightsail private key was not downloaded to `~/.ssh`.

Fix:

- Downloaded the region-specific Lightsail key from `Lightsail > Account > SSH keys`.
- Moved it to `~/.ssh`.
- Set permissions with `chmod 400`.
- Connected with `ssh -i ~/.ssh/LightsailDefaultKey-us-east-2.pem`.

### `visitorbot` Could Not Open Interactive Shell

Issue:

Running:

```bash
sudo -iu visitorbot
```

returned:

```text
This account is currently not available.
```

Cause:

`visitorbot` is a system service user with no login shell.

Fix:

- Kept `ubuntu` as the admin shell user.
- Ran app commands with `sudo -u visitorbot`.
- Added directory permissions for admin inspection.

### systemd Could Not Start Gunicorn

Issue:

The app service failed with:

```text
status=203/EXEC
```

Cause:

Gunicorn was not installed in the server virtual environment, and multiline
`ExecStart` can be easy to misformat.

Fix:

- Installed Gunicorn into `.venv`.
- Documented a single-line `ExecStart` fallback.
- Added checks for `.venv/bin/gunicorn`.

### Mac Screen Sharing Required A Password

Issue:

macOS Screen Sharing requested a password for `localhost` even though x11vnc
was configured with `-nopw`.

Fix:

- Kept x11vnc bound to localhost for safety.
- Added noVNC over SSH tunnel as the recommended Mac access method:

```bash
ssh -i ~/.ssh/LightsailDefaultKey-us-east-2.pem -L 6080:localhost:6080 ubuntu@16.58.134.55
```

- Opened `http://localhost:6080/vnc.html` on the Mac.

### Missing Apartment Number Field

Issue:

The Register2Park visitor form needs an apartment/unit number, but the original
request model did not include it.

Fix:

- Added `apartment_number` to the API schema.
- Added `apartment_number` to the SQLAlchemy model.
- Passed it into the Playwright automation.
- Added local SQLite compatibility handling for the new column.

### Preferred Registration Time Was The Wrong Scheduling Anchor

Issue:

The original scheduler asked for `preferred_registration_time`, but daily
parking registration expires from the actual successful registration time.

Fix:

- Removed preferred time from the UI/API flow.
- New registrations start as `PENDING`.
- First attempt runs immediately.
- First successful timestamp becomes the schedule anchor:
  - `first_registered_at`
  - `last_registered_at`
  - `expires_at = success + 24 hours`
  - `next_registration_at = success + 24 hours`

### Register2Park Property Search Did Not Show Suggestions

Issue:

The bot filled the property search field but failed because no suggestion list
appeared.

Fix:

- Made suggestions optional.
- If the typed property stays in the field and `Next` is visible, automation
continues.

### Matching Property Confirmation Page

Issue:

After clicking `Next`, Register2Park displayed a matching-property confirmation
page with a `Select` button.

Fix:

- Added logic to detect and click the matching property `Select` button.
- Continued only after the confirmation page completed.

### CAPTCHA Appeared After Property Or Vehicle Submission

Issue:

Register2Park showed a reCAPTCHA iframe during the flow.

Fix:

- The bot does not bypass CAPTCHA.
- Automation now pauses in the same headed browser.
- UI shows that manual CAPTCHA completion is required.
- After the user completes CAPTCHA manually, automation resumes from the same
  page/session.
- Added runtime status polling through `/registrations/{id}/runtime-status`.

### Scheduler Tried To Pick Up A Registration While Automation Was Running

Issue:

The scheduler could see a due registration while the first background attempt
was still running.

Fix:

- Added an in-process running-attempt guard.
- If an attempt is already running for a registration, the scheduler skips it.

### Approval Page Was Mistaken For Missing Email

Issue:

Register2Park sometimes shows an `Approved for 24 hours` confirmation page
before an email form appears. The bot originally failed while looking for an
email input.

Fix:

- Added success markers:
  - `approved for 24 hours`
  - `approved to park`
  - `confirmation code`
- Updated email flow to click `E-Mail Confirmation`, enter the provided email,
  and submit it when that option is available.

### Repeated Confirmation Emails During Failed Verification

Issue:

If Register2Park accepted the email confirmation step but the bot could not
verify final success afterward, the registration stayed retryable. With a
two-hour scheduler interval, that could send another confirmation email on
each retry cycle.

Fix:

- Added `ACTION_REQUIRED` registration status.
- Added non-retryable automation results after email submission.
- When email is submitted but final success is not verified:
  - the attempt is recorded
  - `next_registration_at` is cleared
  - scheduler retries are paused
  - UI shows a manual-review message
  - user can intentionally click `Retry now`
- Added `POST /registrations/{id}/retry` for deliberate manual retries.

### Documentation Drift

Issue:

The project changed from a generic selector MVP to a concrete Register2Park
workflow, but the docs still described older behavior.

Fix:

- Rewrote the README as a project overview.
- Added focused docs:
  - [SETUP.md](SETUP.md)
  - [DEPLOYMENT.md](DEPLOYMENT.md)
  - [API.md](API.md)
  - [AUTOMATION.md](AUTOMATION.md)
  - [DATABASE.md](DATABASE.md)
  - [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## Current Capabilities

- Local FastAPI app with browser UI.
- SQLite persistence for registrations and attempts.
- Immediate first registration attempt after submit.
- Daily scheduling from actual success timestamp.
- Headed Playwright automation for Register2Park.
- Manual CAPTCHA pause/resume.
- Screenshot capture for each major transition and failure.
- Email confirmation flow after approval page.
- Cancel endpoint and UI reset button.
- API docs through FastAPI Swagger UI.
- Unit tests for scheduling/business logic.

## Known Limitations

- The app is local-only and has no authentication.
- SQLite schema changes are handled with lightweight compatibility checks, not
  formal migrations.
- Runtime status is in memory; it resets when the server restarts.
- Selectors may need updates if Register2Park changes its UI.
- CAPTCHA requires manual completion.
- There is no full browser integration test against Register2Park because that
  would require real site interaction and manual CAPTCHA.
- Screenshots are local files and not viewable directly in the UI yet.

## Future Improvements

### UI Improvements

- Add a registrations table on the homepage.
- Add live attempt history per registration.
- Add screenshot links in the UI.
- Add a cancel button for saved registrations, not only form reset.
- Add filtering by status: `PENDING`, `ACTIVE`, `FAILED`, `COMPLETED`,
  `CANCELLED`.
- Add a clearer manual action banner for CAPTCHA and other blockers.

### Automation Improvements

- Add more resilient selectors based on observed Register2Park page variants.
- Add optional screenshot comparison notes for debugging selector failures.
- Save the exact confirmation code as a dedicated database column.
- Add a manual “continue after CAPTCHA” button as a fallback to automatic
  resume detection.
- Add safer retry limits so failed registrations do not retry forever.

### Scheduler Improvements

- Add max retry count and exponential backoff.
- Add explicit retry reason fields.
- Add a scheduler dashboard.
- Add timezone-aware timestamps.
- Add a manual “run now” endpoint for a saved registration.

### Database Improvements

- Add Alembic migrations.
- Add indexes on `status` and `next_registration_at`.
- Add dedicated `confirmation_code` column.
- Add an `automation_state` or `last_error` column for easier UI display.

### Testing Improvements

- Add API route tests with FastAPI `TestClient`.
- Add unit tests for runtime status updates.
- Add Playwright tests against a local mock Register2Park page.
- Add tests for CAPTCHA pause/resume behavior using a fake page.

### Deployment Improvements

- Add a launch script for macOS.
- Add optional `launchd` configuration for local startup.
- Add structured JSON logging.
- Add backup instructions for `visitor_parking.db`.

## GitHub Readiness Checklist

Before pushing publicly:

- Confirm `.env` is not staged.
- Confirm `visitor_parking.db` is not staged.
- Confirm screenshots with personal data are not staged.
- Run tests:

```bash
pytest
```

- Review staged files:

```bash
git status
git diff --cached --name-only
```

The project `.gitignore` already excludes the local environment, database, and
PNG screenshots.
