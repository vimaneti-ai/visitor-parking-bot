# Troubleshooting

## `ERROR: [Errno 48] Address already in use`

Port `8000` is already occupied.

Options:

```bash
uvicorn app.main:app --reload --port 8001
```

Or stop the old server with `Ctrl+C` in the terminal running it.

## SQLite Says `no such table: registrations`

You probably opened the wrong database from your home folder.

Wrong:

```bash
cd ~
sqlite3 visitor_parking.db
```

Correct:

```bash
cd /Users/vinod/Projects/visitor-parking-bot
sqlite3 visitor_parking.db
```

Or:

```bash
sqlite3 /Users/vinod/Projects/visitor-parking-bot/visitor_parking.db
```

## Browser Does Not Open

Install Chromium for Playwright:

```bash
source .venv/bin/activate
playwright install chromium
```

Confirm `.env` has:

```env
PLAYWRIGHT_HEADLESS=false
```

## CAPTCHA Appears

This is expected.

The automation pauses and leaves the browser open. Complete CAPTCHA manually.
The UI should show that manual CAPTCHA completion is required. After completion,
the automation resumes from the same page.

If it times out, increase:

```env
MANUAL_CAPTCHA_TIMEOUT_SECONDS=600
```

Then restart uvicorn.

## Email Confirmation Is Not Submitted

The automation tries this sequence:

1. Fill an email field if already visible.
2. If approval page is visible, click `E-Mail Confirmation`.
3. Fill the email field.
4. Click a send/submit/email/continue button.

If it fails, inspect the latest screenshot in `screenshots/` and update
selectors in `enter_email()` inside `app/automation/register2park_bot.py`.

## Property Selection Fails

Register2Park can show:

- A search field with no visible suggestions.
- A matching property confirmation page.
- A `Select` button for the matched property.

The automation handles all three, but if the UI changes, inspect the latest
`property` or `matching_property` screenshot and update `select_property()`.

## Registration Says `FAILED`

Check attempts:

```sql
SELECT registration_id, attempted_at, status, message, screenshot_path
FROM registration_attempts
ORDER BY attempted_at DESC;
```

Then open the latest screenshot path.

## Scheduler Did Not Run

Confirm the FastAPI app is running. The scheduler starts with app startup.

Check:

```text
http://127.0.0.1:8000/health
```

Confirm the registration is due:

```sql
SELECT id, status, next_registration_at
FROM registrations
ORDER BY created_at DESC;
```

Only `PENDING` and `ACTIVE` registrations with `next_registration_at <= now`
are processed.

## Tests

Run:

```bash
source .venv/bin/activate
pytest
```

Expected:

```text
7 passed
```
