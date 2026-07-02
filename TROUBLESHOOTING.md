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

On AWS, solve CAPTCHA through noVNC:

```bash
ssh -i ~/.ssh/LightsailDefaultKey-us-east-2.pem -L 6080:localhost:6080 ubuntu@YOUR_STATIC_IP
```

Then open on your Mac:

```text
http://localhost:6080/vnc.html
```

Keep the SSH tunnel terminal open.

## AWS SSH Says `Permission denied (publickey)`

The server is reachable, but your Mac is not using the Lightsail private key.

Download the key from:

```text
Lightsail > Account > SSH keys
```

Use the key for the same region as the instance, for example Ohio/us-east-2:

```bash
mkdir -p ~/.ssh
mv ~/Downloads/LightsailDefaultKey-us-east-2.pem ~/.ssh/
chmod 400 ~/.ssh/LightsailDefaultKey-us-east-2.pem
ssh -i ~/.ssh/LightsailDefaultKey-us-east-2.pem ubuntu@YOUR_STATIC_IP
```

## `sudo -iu visitorbot` Says Account Not Available

This is expected. `visitorbot` is a system service user and does not have an
interactive login shell.

Run commands as `ubuntu`, and prefix app commands with:

```bash
sudo -u visitorbot
```

Example:

```bash
cd /opt/visitor-parking-bot/appsrc
sudo -u visitorbot .venv/bin/pip install -r requirements.txt
```

## Git Says `detected dubious ownership`

The repo is owned by `visitorbot`, but you are inspecting it as `ubuntu`.

Fix:

```bash
git config --global --add safe.directory /opt/visitor-parking-bot/appsrc
```

## `cd /opt/visitor-parking-bot/appsrc` Says Permission Denied

Allow the admin user to enter/read the app directory:

```bash
sudo chmod o+x /opt/visitor-parking-bot
sudo chmod -R o+rX /opt/visitor-parking-bot/appsrc
```

## systemd Shows `status=203/EXEC`

systemd could not execute the command in `ExecStart`.

Check Gunicorn:

```bash
ls -la /opt/visitor-parking-bot/appsrc/.venv/bin/gunicorn
```

If missing:

```bash
cd /opt/visitor-parking-bot/appsrc
sudo -u visitorbot .venv/bin/pip install gunicorn
```

Also make `ExecStart` one single line in:

```bash
sudo nano /etc/systemd/system/visitor-parking-bot.service
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart visitor-parking-bot
sudo systemctl status visitor-parking-bot
```

## AWS SQLite Says `unable to open database file`

The production database is usually owned by `visitorbot`.

Use:

```bash
sudo sqlite3 /opt/visitor-parking-bot/data/visitor_parking.db
```

Inspect:

```bash
sudo ls -la /opt/visitor-parking-bot/data
sudo cat /opt/visitor-parking-bot/appsrc/.env
```

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
