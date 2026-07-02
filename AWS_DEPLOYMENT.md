# AWS Deployment Guide

This guide deploys the Visitor Parking Bot to AWS so it can run continuously
with FastAPI, SQLite, Playwright Chromium, APScheduler, logging, screenshots,
HTTPS, remote browser access for manual CAPTCHA, and automatic restart after
reboot.

The recommended beginner-friendly AWS target for this project is **Amazon
Lightsail Ubuntu**.

## Important Safety Note

This project must not bypass CAPTCHA, OTP, login, payment, or other security
checks. In cloud deployment, CAPTCHA requires manual completion through a
remote desktop/VNC-style browser session. For this project, set up VNC/noVNC
during the first AWS deployment so you can see the remote Chromium browser
when manual CAPTCHA completion is required.

## Current Project Analysis

### Current Architecture

```text
Browser UI
  -> FastAPI app
    -> SQLite database
    -> APScheduler background jobs
    -> Playwright Chromium automation
    -> local screenshots directory
```

Key files:

- `app/main.py`: FastAPI app, local UI, API routes, startup/shutdown lifecycle.
- `app/config.py`: environment-backed configuration.
- `app/database.py`: SQLAlchemy engine/session and table creation.
- `app/models.py`: `registrations` and `registration_attempts`.
- `app/scheduler.py`: APScheduler jobs.
- `app/services/registration_service.py`: create/cancel/attempt/schedule logic.
- `app/services/runtime_status.py`: live in-memory automation status for UI.
- `app/automation/register2park_bot.py`: Playwright Register2Park automation.
- `app/static/index.html`: local web UI.

### Runtime Requirements

- Linux server
- Python 3.11+
- pip and venv
- Git
- SQLite
- Playwright Chromium
- Linux browser dependencies
- Nginx
- Gunicorn with Uvicorn worker
- systemd
- Certbot for HTTPS
- VNC/noVNC for manual CAPTCHA

### Python Version

The app has been tested locally with Python 3.11. Use Ubuntu 24.04 and install
Python 3.12 from Ubuntu packages, or Ubuntu 22.04 with Python 3.10+. Python
3.11 or 3.12 is recommended.

Playwright supports Python 3.8+ and Ubuntu 22.04/24.04 according to its
official docs. Source: https://playwright.dev/python/docs/intro

### Python Dependencies

From `requirements.txt`:

```text
fastapi
uvicorn
gunicorn
pydantic
email-validator
pydantic-settings
SQLAlchemy
APScheduler
playwright
python-dotenv
pytest
httpx
```

### Environment Variables

Production `.env` should contain:

```env
DATABASE_URL=sqlite:////opt/visitor-parking-bot/data/visitor_parking.db
SCREENSHOT_DIR=/opt/visitor-parking-bot/screenshots
SCREENSHOT_RETENTION_HOURS=24

REGISTER2PARK_URL=https://www.register2park.com/
REGISTER2PARK_PROPERTY_NAME=Lakeside Urban Center Apartments

PLAYWRIGHT_HEADLESS=false
PLAYWRIGHT_TIMEOUT_MS=30000
MANUAL_CAPTCHA_TIMEOUT_SECONDS=300

SCHEDULER_INTERVAL_SECONDS=7200
SCREENSHOT_CLEANUP_INTERVAL_SECONDS=3600
RETRY_DELAY_MINUTES=30

LOG_LEVEL=INFO
```

### Database Requirements

SQLite is sufficient for this project because:

- Single user
- Single app process
- Low write volume
- Simple deployment
- Data fits in one local file

Use PostgreSQL later if:

- Multiple users
- Multiple app instances
- Remote dashboard users
- Stronger backups/replication
- Concurrent writes become important

### Scheduler Requirements

APScheduler starts inside FastAPI startup. For production, run **one Gunicorn
worker only**. Multiple workers would start multiple schedulers and could
duplicate attempts.

### Storage Requirements

Persistent storage is needed for:

- SQLite database
- screenshots
- logs/backups

Lightsail instance SSD is enough initially.

### Browser Requirements

Playwright Chromium must be installed on the server. Because the app pauses for
manual CAPTCHA, cloud deployment needs either:

- Headed Chromium with a virtual display such as Xvfb
- VNC/noVNC to see and control the browser remotely

## Should Anything Change Before Deployment?

Recommended before AWS deployment:

1. Keep `gunicorn` in `requirements.txt`.
2. Use `DATABASE_URL=sqlite:////opt/visitor-parking-bot/data/visitor_parking.db`.
3. Use absolute screenshot path: `/opt/visitor-parking-bot/screenshots`.
4. Run only one Gunicorn worker.
5. Add backups for SQLite and screenshots.
6. Restrict direct app port access; expose only Nginx ports 80/443.
7. Use HTTPS before entering real personal/vehicle data over the public web.
8. Use VNC/noVNC only behind SSH tunnel or strict firewall rules.

## AWS Architecture Comparison

### Lightsail

Pros:

- Easiest for beginners.
- Fixed monthly pricing.
- Includes SSD, networking allowance, DNS tools, static IP.
- Simple SSH access.
- Good fit for one small always-on app.

Cons:

- Less flexible than EC2.
- Scaling is manual.
- You manage OS updates and security.

Best for this project: **Yes**.

### EC2

Pros:

- Full AWS control.
- More instance types.
- More networking/IAM options.
- Good for serious production systems.

Cons:

- More AWS complexity.
- Public IPv4 can add cost.
- EBS, security groups, IAM, monitoring all need more attention.

Best for this project: Good, but more complex than needed.

### ECS

Pros:

- Container-native deployment.
- Easier rolling deploys.
- Good for scalable services.

Cons:

- More moving parts.
- Browser automation and manual CAPTCHA/VNC are awkward in containers.
- Scheduler needs careful single-instance design.

Best for this project: Not recommended initially.

### App Runner

Pros:

- Simple container/web app hosting.
- HTTPS is managed.
- Easy deployments.

Cons:

- Not designed for headed browser/manual CAPTCHA.
- Persistent local SQLite/screenshot storage is not a good fit.
- Long-running scheduler/background jobs are awkward.

Best for this project: Not recommended.

### Elastic Beanstalk

Pros:

- Managed EC2 deployment pattern.
- Supports Python web apps.
- Can use Nginx and system services.

Cons:

- More complex than Lightsail.
- Background scheduler plus browser automation still needs care.
- Less beginner-friendly for this use case.

Best for this project: Possible, but not the best first deployment.

## Recommended Architecture

Use **Amazon Lightsail Ubuntu 24.04, 2 GB RAM**.

```text
User Browser
  -> HTTPS
  -> Nginx
  -> Gunicorn + Uvicorn worker
  -> FastAPI app
  -> SQLite database on local SSD
  -> APScheduler
  -> Playwright Chromium on Xvfb display
  -> screenshots directory

Admin Browser / VNC Viewer
  -> SSH tunnel or restricted VNC/noVNC
  -> remote Chromium for manual CAPTCHA
```

## Cost Estimate

AWS Lightsail pricing lists bundled plans with predictable monthly prices.
The 2 GB Linux plan with public IPv4 is listed at `$12/month` with 2 vCPUs,
60 GB SSD, and 3 TB transfer. Source: https://aws.amazon.com/lightsail/pricing/

Estimated monthly cost:

| Item | Estimate | Notes |
| --- | ---: | --- |
| Lightsail 2 GB Linux | `$12/month` | Recommended |
| SSD storage | Included | 60 GB in plan |
| Static IP | Included in Lightsail features | AWS lists static IP as included in Lightsail plans |
| DNS in Lightsail | Included | Or use Cloudflare/IONOS |
| SSL certificate | Free | Let's Encrypt/Certbot |
| Domain | `$10-$20/year` | Optional, registrar-dependent |
| Snapshots/backups | Extra | Depends on snapshot size |
| RDS/Postgres | Not needed initially | Would add cost |

Likely cost:

```text
Without domain/backups: about $12/month
With basic backups/domain averaged monthly: about $15-$20/month
```

AWS also documents public IPv4 pricing at `$0.005/hour` for VPC public IPv4
addresses. Lightsail bundles are simpler, but this matters if using EC2.
Source: https://aws.amazon.com/vpc/pricing/

## Step 1: Create AWS Account

1. Go to `https://aws.amazon.com/`.
2. Click **Create an AWS Account**.
3. Enter email, account name, contact details, and payment method.
4. Complete identity verification.
5. Sign in to the AWS Console.

Set a billing alarm:

1. Search for **Billing and Cost Management**.
2. Go to **Budgets**.
3. Create a monthly budget, for example `$20`.
4. Add email alerts at 50%, 80%, and 100%.

## Step 2: Choose Region

Use a region near you, for example:

```text
us-east-1      N. Virginia
us-east-2      Ohio
us-west-2      Oregon
```

For Texas/Central US, `us-east-2` or `us-east-1` is fine.

## Step 3: Create Lightsail Server

1. Open AWS Console.
2. Search **Lightsail**.
3. Click **Create instance**.
4. Choose **Linux/Unix**.
5. Choose **OS Only**.
6. Choose **Ubuntu 24.04 LTS**.
7. Choose plan:

```text
2 GB RAM / 2 vCPU / 60 GB SSD / $12 month
```

8. Name instance:

```text
visitor-parking-bot
```

9. Click **Create instance**.

## Step 4: Attach Static IP

1. In Lightsail, go to **Networking**.
2. Click **Create static IP**.
3. Attach it to `visitor-parking-bot`.
4. Name it:

```text
visitor-parking-bot-ip
```

Keep this IP. You will use it for DNS.

## Step 5: Open Firewall Ports

In Lightsail instance networking:

Allow:

```text
22/tcp    SSH
80/tcp    HTTP
443/tcp   HTTPS
```

Do not publicly open VNC ports unless you understand the risk. Prefer SSH
tunneling for VNC/noVNC.

## Step 6: SSH Into Server

From Lightsail console, click **Connect using SSH**.

Or from your Mac terminal:

```bash
ssh ubuntu@YOUR_STATIC_IP
```

If using a downloaded key:

```bash
mkdir -p ~/.ssh
mv ~/Downloads/LightsailDefaultKey-us-east-2.pem ~/.ssh/
chmod 400 ~/.ssh/LightsailDefaultKey-us-east-2.pem
ssh -i ~/.ssh/LightsailDefaultKey-us-east-2.pem ubuntu@YOUR_STATIC_IP
```

Use the key for the same region as your instance. This deployment used
`us-east-2` / Ohio, so the key name was `LightsailDefaultKey-us-east-2.pem`.

If you see:

```text
Permission denied (publickey)
```

the server is reachable, but your Mac is not using the correct private key.
Download the key from **Lightsail > Account > SSH keys**, not from the general
AWS account page.

## Step 7: Update Ubuntu

```bash
sudo apt update
sudo apt upgrade -y
sudo reboot
```

Reconnect after reboot:

```bash
ssh ubuntu@YOUR_STATIC_IP
```

## Step 8: Install System Packages

```bash
sudo apt update
sudo apt install -y \
  python3 \
  python3-venv \
  python3-pip \
  git \
  sqlite3 \
  nginx \
  ufw \
  fail2ban \
  unzip \
  curl \
  ca-certificates \
  xvfb \
  x11vnc \
  novnc \
  websockify
```

What this installs:

- `python3`, `python3-venv`, `python3-pip`: Python runtime.
- `git`: clone/update the repo.
- `sqlite3`: inspect and back up DB.
- `nginx`: reverse proxy and static TLS entrypoint.
- `ufw`: local firewall.
- `fail2ban`: SSH brute-force protection.
- `xvfb`: virtual display for headed Chromium.
- `x11vnc`, `novnc`, `websockify`: remote browser access for CAPTCHA.

## Step 9: Create Application User And Directories

```bash
sudo adduser --system --group --home /opt/visitor-parking-bot visitorbot
sudo mkdir -p /opt/visitor-parking-bot
sudo mkdir -p /opt/visitor-parking-bot/data
sudo mkdir -p /opt/visitor-parking-bot/screenshots
sudo mkdir -p /opt/visitor-parking-bot/backups
sudo chown -R visitorbot:visitorbot /opt/visitor-parking-bot
```

## Step 10: Clone GitHub Repository

Switch to `/opt`:

```bash
cd /opt
```

Clone the repo:

```bash
sudo -u visitorbot git clone https://github.com/vimaneti-ai/visitor-parking-bot.git /opt/visitor-parking-bot/appsrc
```

Allow the `ubuntu` admin user to enter and inspect the app directory while
keeping `visitorbot` as the owner:

```bash
sudo chmod o+x /opt/visitor-parking-bot
sudo chmod -R o+rX /opt/visitor-parking-bot/appsrc
git config --global --add safe.directory /opt/visitor-parking-bot/appsrc
```

Why this is needed:

- `visitorbot` is a system service user and cannot open an interactive shell.
- `sudo -iu visitorbot` may show `This account is currently not available`.
- Git may show `detected dubious ownership` when `ubuntu` inspects a repo owned
  by `visitorbot`.

If the directory already exists:

```bash
cd /opt/visitor-parking-bot/appsrc
sudo -u visitorbot git pull
```

## Step 11: Create Virtual Environment

```bash
cd /opt/visitor-parking-bot/appsrc
sudo -u visitorbot python3 -m venv .venv
sudo -u visitorbot .venv/bin/pip install --upgrade pip
sudo -u visitorbot .venv/bin/pip install -r requirements.txt
```

Verify Gunicorn exists because systemd uses it:

```bash
ls -la /opt/visitor-parking-bot/appsrc/.venv/bin/gunicorn
```

If it is missing:

```bash
sudo -u visitorbot .venv/bin/pip install gunicorn
```

## Step 12: Install Playwright Browsers And Dependencies

Playwright docs install browsers with `playwright install`. Source:
https://playwright.dev/python/docs/intro

Run:

```bash
cd /opt/visitor-parking-bot/appsrc
sudo -u visitorbot .venv/bin/playwright install chromium
sudo .venv/bin/playwright install-deps chromium
```

`install-deps` installs Linux packages needed by Chromium. `install chromium`
downloads the Playwright-managed Chromium browser.

## Step 13: Create Production `.env`

```bash
sudo -u visitorbot nano /opt/visitor-parking-bot/appsrc/.env
```

Paste:

```env
DATABASE_URL=sqlite:////opt/visitor-parking-bot/data/visitor_parking.db
SCREENSHOT_DIR=/opt/visitor-parking-bot/screenshots
SCREENSHOT_RETENTION_HOURS=24

REGISTER2PARK_URL=https://www.register2park.com/
REGISTER2PARK_PROPERTY_NAME=Lakeside Urban Center Apartments

PLAYWRIGHT_HEADLESS=false
PLAYWRIGHT_TIMEOUT_MS=30000
MANUAL_CAPTCHA_TIMEOUT_SECONDS=300

SCHEDULER_INTERVAL_SECONDS=7200
SCREENSHOT_CLEANUP_INTERVAL_SECONDS=3600
RETRY_DELAY_MINUTES=30

LOG_LEVEL=INFO
```

Secure it:

```bash
sudo chown visitorbot:visitorbot /opt/visitor-parking-bot/appsrc/.env
sudo chmod 600 /opt/visitor-parking-bot/appsrc/.env
```

## Step 14: Initialize Database

```bash
cd /opt/visitor-parking-bot/appsrc
sudo -u visitorbot .venv/bin/python -c "from app.database import init_db; init_db()"
```

Verify:

```bash
sudo sqlite3 /opt/visitor-parking-bot/data/visitor_parking.db ".tables"
```

Expected:

```text
registration_attempts  registrations
```

## Step 15: Test App Manually

```bash
cd /opt/visitor-parking-bot/appsrc
sudo -u visitorbot DISPLAY=:99 .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another SSH session:

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok"}
```

Stop the manual server with `Ctrl+C`.

## Step 16: Create Xvfb systemd Service

Create:

```bash
sudo nano /etc/systemd/system/visitor-parking-xvfb.service
```

Paste:

```ini
[Unit]
Description=Virtual display for Visitor Parking Bot
After=network.target

[Service]
User=visitorbot
Group=visitorbot
ExecStart=/usr/bin/Xvfb :99 -screen 0 1280x1024x24
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Explanation:

- `Description`: name shown in systemctl.
- `After=network.target`: starts after basic networking.
- `User`/`Group`: runs as the non-login app user.
- `ExecStart`: starts virtual display `:99`.
- `Restart=always`: restarts if Xvfb crashes.
- `WantedBy`: starts at normal boot.

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable visitor-parking-xvfb
sudo systemctl start visitor-parking-xvfb
sudo systemctl status visitor-parking-xvfb
```

## Step 17: Create FastAPI systemd Service

Create:

```bash
sudo nano /etc/systemd/system/visitor-parking-bot.service
```

Paste:

```ini
[Unit]
Description=Visitor Parking Bot FastAPI service
After=network.target visitor-parking-xvfb.service
Requires=visitor-parking-xvfb.service

[Service]
User=visitorbot
Group=visitorbot
WorkingDirectory=/opt/visitor-parking-bot/appsrc
Environment=DISPLAY=:99
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/visitor-parking-bot/appsrc/.venv/bin/gunicorn app.main:app \
  --workers 1 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 127.0.0.1:8000 \
  --timeout 600 \
  --access-logfile - \
  --error-logfile -
Restart=always
RestartSec=10
KillSignal=SIGINT
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

If your systemd service fails with `status=203/EXEC`, rewrite `ExecStart` as
one single line and confirm Gunicorn exists in `.venv/bin/gunicorn`:

```ini
ExecStart=/opt/visitor-parking-bot/appsrc/.venv/bin/gunicorn app.main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000 --timeout 600 --access-logfile - --error-logfile -
```

Explanation:

- `After`: app starts after network and Xvfb.
- `Requires`: if Xvfb cannot start, app does not start.
- `WorkingDirectory`: where `.env` is read from.
- `DISPLAY=:99`: Chromium uses the virtual display.
- `PYTHONUNBUFFERED=1`: logs appear immediately.
- `gunicorn app.main:app`: production ASGI server.
- `--workers 1`: required because APScheduler lives in the app process.
- `UvicornWorker`: lets Gunicorn serve FastAPI.
- `--bind 127.0.0.1:8000`: app only listens locally; Nginx exposes it.
- `--timeout 600`: allows long CAPTCHA/manual automation waits.
- `Restart=always`: auto-restart on crash.

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable visitor-parking-bot
sudo systemctl start visitor-parking-bot
sudo systemctl status visitor-parking-bot
```

Check health:

```bash
curl http://127.0.0.1:8000/health
```

## Step 18: Configure Nginx Reverse Proxy

Create:

```bash
sudo nano /etc/nginx/sites-available/visitor-parking-bot
```

Replace `yourdomain.com` with your domain:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600;
        proxy_connect_timeout 60;
        proxy_send_timeout 600;
    }
}
```

Enable:

```bash
sudo ln -s /etc/nginx/sites-available/visitor-parking-bot /etc/nginx/sites-enabled/visitor-parking-bot
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

## Step 19: Configure Firewall

Lightsail firewall should allow 22, 80, 443.

Server firewall:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

## Step 20: Configure HTTPS With Let's Encrypt

Certbot official Nginx instructions install Certbot via snap and run
`sudo certbot --nginx`. Source: https://certbot.eff.org/instructions?ws=nginx&os=snap

Install:

```bash
sudo snap install core
sudo snap refresh core
sudo apt-get remove -y certbot || true
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/local/bin/certbot
```

Get certificate:

```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Test renewal:

```bash
sudo certbot renew --dry-run
```

Verify:

```text
https://yourdomain.com
```

## Step 21: Domain Setup

Use your Lightsail static IP as the target.

### Route 53

1. Open Route 53.
2. Create hosted zone for `yourdomain.com`.
3. Add records:

```text
Type: A
Name: yourdomain.com
Value: YOUR_STATIC_IP
TTL: 300

Type: A
Name: www.yourdomain.com
Value: YOUR_STATIC_IP
TTL: 300
```

4. Copy Route 53 nameservers to your domain registrar.

### Cloudflare

1. Add site to Cloudflare.
2. Update registrar nameservers to Cloudflare nameservers.
3. Add DNS records:

```text
A     @      YOUR_STATIC_IP      DNS only or Proxied
A     www    YOUR_STATIC_IP      DNS only or Proxied
```

For initial Certbot setup, use **DNS only** if certificate issues occur. After
HTTPS works, you can enable Cloudflare proxy if desired.

### IONOS

1. Log in to IONOS.
2. Go to Domains & SSL.
3. Open DNS settings.
4. Add/update:

```text
A     @      YOUR_STATIC_IP
A     www    YOUR_STATIC_IP
```

5. Wait for DNS propagation.

Check DNS:

```bash
dig yourdomain.com
dig www.yourdomain.com
```

## Step 22: Set Up VNC/noVNC For Manual CAPTCHA

This step lets you see and control Chromium running on the AWS server. It is
needed because this project must pause for human CAPTCHA completion instead of
bypassing CAPTCHA.

Use an SSH tunnel. Do not open VNC or noVNC ports publicly.

### Create x11vnc Service

x11vnc shares the Xvfb display `:99`, which is where Playwright Chromium runs.

Create:

```bash
sudo nano /etc/systemd/system/visitor-parking-x11vnc.service
```

Paste:

```ini
[Unit]
Description=VNC access to Visitor Parking Bot browser display
After=visitor-parking-xvfb.service
Requires=visitor-parking-xvfb.service

[Service]
User=visitorbot
Group=visitorbot
ExecStart=/usr/bin/x11vnc -display :99 -localhost -forever -shared -nopw -rfbport 5900
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Explanation:

- `After`/`Requires`: x11vnc starts only after the virtual display exists.
- `-display :99`: shares the same display used by Playwright Chromium.
- `-localhost`: listens only on the server itself, not the public internet.
- `-forever`: keeps running after a VNC viewer disconnects.
- `-shared`: allows reconnecting without killing the session.
- `-nopw`: acceptable only because access is restricted to localhost and SSH tunnel.
- `-rfbport 5900`: VNC listens on port `5900` locally.

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable visitor-parking-x11vnc
sudo systemctl start visitor-parking-x11vnc
sudo systemctl status visitor-parking-x11vnc
```

### Connect From Your Mac With VNC

Open a new terminal on your Mac:

```bash
ssh -i ~/.ssh/LightsailDefaultKey-us-east-2.pem -L 5900:localhost:5900 ubuntu@YOUR_STATIC_IP
```

Keep that SSH tunnel open.

Then open a VNC viewer on your Mac and connect to:

```text
localhost:5900
```

When the automation pauses for CAPTCHA, the Chromium window should be visible
there. Solve the CAPTCHA manually. The app should detect completion and resume
from the same page.

Do not run the tunnel command inside the AWS terminal. If your prompt looks
like `ubuntu@ip-...`, you are already on the AWS server. The tunnel command
must be run from your Mac terminal.

If macOS Screen Sharing asks for a password and will not accept blank, use
noVNC below instead.

### Create noVNC Service

noVNC lets you use a browser instead of a VNC desktop app.

Create:

```bash
sudo nano /etc/systemd/system/visitor-parking-novnc.service
```

Paste:

```ini
[Unit]
Description=Browser-based noVNC access for Visitor Parking Bot
After=visitor-parking-x11vnc.service
Requires=visitor-parking-x11vnc.service

[Service]
User=visitorbot
Group=visitorbot
ExecStart=/usr/bin/websockify --web=/usr/share/novnc 127.0.0.1:6080 127.0.0.1:5900
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Explanation:

- `websockify`: bridges browser WebSocket traffic to VNC.
- `--web=/usr/share/novnc`: serves the noVNC web files.
- `127.0.0.1:6080`: noVNC listens only locally.
- `127.0.0.1:5900`: connects to local x11vnc.

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable visitor-parking-novnc
sudo systemctl start visitor-parking-novnc
sudo systemctl status visitor-parking-novnc
```

Open a new terminal on your Mac:

```bash
ssh -i ~/.ssh/LightsailDefaultKey-us-east-2.pem -L 6080:localhost:6080 ubuntu@YOUR_STATIC_IP
```

Keep that tunnel open, then open this on your Mac:

```text
http://localhost:6080/vnc.html
```

Click connect. If it asks for a host, use:

```text
localhost:6080
```

If it asks for a VNC password, leave it blank and connect. The x11vnc service
uses `-nopw`, but access is protected by the SSH tunnel.

### Manual Test

You can also start x11vnc manually for quick troubleshooting:

```bash
sudo -u visitorbot x11vnc -display :99 -localhost -forever -shared -nopw
```

From your Mac in another terminal:

```bash
ssh -L 5900:localhost:5900 ubuntu@YOUR_STATIC_IP
```

Open a VNC viewer on your Mac:

```text
localhost:5900
```

Security rule: do not expose VNC/noVNC publicly without authentication and
firewall rules. The recommended setup is SSH tunnel only.

## Logging

### Application Logs

The app logs to stdout/stderr. systemd captures them.

View:

```bash
sudo journalctl -u visitor-parking-bot -f
```

Last 200 lines:

```bash
sudo journalctl -u visitor-parking-bot -n 200 --no-pager
```

### Scheduler Logs

Scheduler logs are in the same service:

```bash
sudo journalctl -u visitor-parking-bot | grep scheduler
```

### Playwright Logs

Playwright step logs are also in the app journal:

```bash
sudo journalctl -u visitor-parking-bot | grep register2park_bot
```

### Nginx Logs

```bash
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Xvfb Logs

```bash
sudo journalctl -u visitor-parking-xvfb -f
```

## Day-To-Day Operations

### Keep The Instance Running

Keep the Lightsail instance running while you want automatic registration to
work. The server must stay on for:

- FastAPI website
- APScheduler jobs
- Playwright automation
- retries
- logs and screenshots
- VNC/noVNC manual CAPTCHA access

If you stop the instance, the website goes offline and the scheduler stops.
Lightsail pricing is monthly for the instance plan while the instance exists,
so stopping is not the same as deleting the monthly resource.

### Check AWS Cost

In AWS Console, open:

```text
Billing and Cost Management > Bills
Billing and Cost Management > Cost Explorer
Billing and Cost Management > Budgets
```

For this deployment, expected baseline cost is the Lightsail instance plan,
for example about `$12/month` for the 2 GB plan, plus taxes. A static IP is
free while attached to a running instance. Let's Encrypt SSL is free. Route 53
or a purchased domain adds separate cost only if you use them.

Create a budget alert:

```text
Budget amount: 15 or 20 USD
Alert threshold: 80%
Email: your email
```

### Check Public App

Without a domain:

```text
http://YOUR_STATIC_IP
```

With a domain and HTTPS:

```text
https://yourdomain.com
```

Certbot needs a domain name for normal HTTPS. It cannot issue the usual public
certificate for only a raw IP address.

## Log Rotation

Nginx log rotation is installed by Ubuntu packages.

systemd journal can be limited:

```bash
sudo nano /etc/systemd/journald.conf
```

Set:

```ini
SystemMaxUse=500M
MaxRetentionSec=14day
```

Restart:

```bash
sudo systemctl restart systemd-journald
```

## Backups

### Manual SQLite Backup

```bash
sudo -u visitorbot sqlite3 /opt/visitor-parking-bot/data/visitor_parking.db ".backup '/opt/visitor-parking-bot/backups/visitor_parking_$(date +%Y%m%d_%H%M%S).db'"
```

### Manual Screenshot Backup

```bash
sudo tar -czf /opt/visitor-parking-bot/backups/screenshots_$(date +%Y%m%d_%H%M%S).tar.gz -C /opt/visitor-parking-bot screenshots
```

### Daily Backup Script

Create:

```bash
sudo nano /usr/local/bin/backup-visitor-parking-bot.sh
```

Paste:

```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/opt/visitor-parking-bot/backups"
DB="/opt/visitor-parking-bot/data/visitor_parking.db"
STAMP="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"
sqlite3 "$DB" ".backup '$BACKUP_DIR/visitor_parking_$STAMP.db'"
tar -czf "$BACKUP_DIR/screenshots_$STAMP.tar.gz" -C /opt/visitor-parking-bot screenshots
find "$BACKUP_DIR" -type f -mtime +14 -delete
```

Enable:

```bash
sudo chmod +x /usr/local/bin/backup-visitor-parking-bot.sh
```

Cron:

```bash
sudo crontab -e
```

Add:

```cron
0 3 * * * /usr/local/bin/backup-visitor-parking-bot.sh
```

### Restore SQLite Backup

Stop app:

```bash
sudo systemctl stop visitor-parking-bot
```

Copy backup:

```bash
sudo cp /opt/visitor-parking-bot/backups/visitor_parking_YYYYMMDD_HHMMSS.db /opt/visitor-parking-bot/data/visitor_parking.db
sudo chown visitorbot:visitorbot /opt/visitor-parking-bot/data/visitor_parking.db
```

Start app:

```bash
sudo systemctl start visitor-parking-bot
```

## Monitoring

Free/simple tools:

- `systemctl`
- `journalctl`
- UptimeRobot free HTTP check
- AWS Lightsail metrics
- AWS billing alerts

Commands:

```bash
sudo systemctl status visitor-parking-bot
sudo systemctl status visitor-parking-xvfb
sudo systemctl status nginx
sudo journalctl -u visitor-parking-bot -f
curl http://127.0.0.1:8000/health
curl https://yourdomain.com/health
```

Restart:

```bash
sudo systemctl restart visitor-parking-bot
```

Detect failures:

```bash
sudo systemctl --failed
sudo journalctl -p err -n 100 --no-pager
```

## Updating The Application

```bash
cd /opt/visitor-parking-bot/appsrc
sudo -u visitorbot git pull
sudo -u visitorbot .venv/bin/pip install -r requirements.txt
sudo .venv/bin/playwright install-deps chromium
sudo -u visitorbot .venv/bin/playwright install chromium
sudo -u visitorbot .venv/bin/python -c "from app.database import init_db; init_db()"
sudo systemctl restart visitor-parking-bot
sudo systemctl status visitor-parking-bot
curl http://127.0.0.1:8000/health
```

What each command does:

- `git pull`: gets latest code.
- `pip install`: installs new dependencies.
- `playwright install-deps`: ensures Linux browser deps exist.
- `playwright install chromium`: ensures Chromium exists.
- `init_db()`: creates/updates SQLite tables.
- `systemctl restart`: reloads app code.
- `curl`: verifies health endpoint.

## Rollback

Find commits:

```bash
cd /opt/visitor-parking-bot/appsrc
sudo -u visitorbot git log --oneline -5
```

Rollback to previous commit:

```bash
sudo -u visitorbot git checkout COMMIT_HASH
sudo -u visitorbot .venv/bin/pip install -r requirements.txt
sudo systemctl restart visitor-parking-bot
curl http://127.0.0.1:8000/health
```

Return to main later:

```bash
sudo -u visitorbot git checkout main
sudo -u visitorbot git pull
sudo systemctl restart visitor-parking-bot
```

## Security Best Practices

### SSH Keys

Use SSH key authentication only. Do not use password SSH.

Edit:

```bash
sudo nano /etc/ssh/sshd_config
```

Set:

```text
PasswordAuthentication no
PermitRootLogin no
```

Restart:

```bash
sudo systemctl restart ssh
```

### Firewall

Allow only SSH, HTTP, HTTPS:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

### Fail2Ban

```bash
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
sudo systemctl status fail2ban
```

### Secrets

- Store secrets in `.env`.
- Use `chmod 600 .env`.
- Do not commit `.env`.
- Do not put real vehicle data in GitHub.

### File Permissions

```bash
sudo chown -R visitorbot:visitorbot /opt/visitor-parking-bot
sudo chmod 700 /opt/visitor-parking-bot/data
sudo chmod 700 /opt/visitor-parking-bot/screenshots
sudo chmod 600 /opt/visitor-parking-bot/appsrc/.env
```

## Playwright Notes

### Headless vs Headed

- `PLAYWRIGHT_HEADLESS=false`: needed for manual CAPTCHA visibility.
- `PLAYWRIGHT_HEADLESS=true`: easier server automation, but manual CAPTCHA is not possible.

### Running As A Service

The app service uses:

```text
Environment=DISPLAY=:99
```

This points Chromium at the Xvfb virtual display.

### Screenshot Storage

Screenshots are stored in:

```text
/opt/visitor-parking-bot/screenshots
```

The app also has screenshot cleanup settings:

```env
SCREENSHOT_RETENTION_HOURS=24
SCREENSHOT_CLEANUP_INTERVAL_SECONDS=3600
```

## Scheduler Behavior

APScheduler starts in `app.main` lifespan startup.

On reboot:

1. systemd starts Xvfb.
2. systemd starts FastAPI.
3. FastAPI calls `start_scheduler()`.
4. Scheduler checks due registrations.
5. Any `PENDING` or `ACTIVE` row with `next_registration_at <= now` is retried.

Completed and cancelled registrations are skipped.

Failed normal attempts retry after:

```env
RETRY_DELAY_MINUTES=30
```

## Disaster Recovery

### Server Reboots

systemd restarts Xvfb and the app. Scheduler resumes on startup.

### AWS Restarts VM

Same as server reboot. Persistent files remain on Lightsail disk.

### Application Crashes

systemd restarts the app because:

```ini
Restart=always
```

### Internet Unavailable

Automation fails and schedules retry. Check logs after network returns.

### Register2Park Unavailable

Attempt fails, screenshot/log is saved, retry is scheduled.

### SQLite Corruption

Stop the app and restore the latest backup from `/opt/visitor-parking-bot/backups`.

## Verification Checklist

### FastAPI

```bash
curl http://127.0.0.1:8000/health
curl https://yourdomain.com/health
```

### Scheduler

```bash
sudo journalctl -u visitor-parking-bot | grep "Scheduler started"
```

### Browser Automation

Submit a test registration from the UI and watch logs:

```bash
sudo journalctl -u visitor-parking-bot -f
```

### Database

```bash
sudo -u visitorbot sqlite3 /opt/visitor-parking-bot/data/visitor_parking.db ".tables"
```

### HTTPS

Open:

```text
https://yourdomain.com
```

Look for browser lock icon.

### Logs

```bash
sudo journalctl -u visitor-parking-bot -n 100 --no-pager
sudo tail -n 100 /var/log/nginx/error.log
```

### Screenshots

```bash
sudo ls -lah /opt/visitor-parking-bot/screenshots
```

### Automatic Registration Timing

```sql
SELECT id, status, registration_count, last_registered_at, expires_at, next_registration_at
FROM registrations
ORDER BY created_at DESC;
```

## Common Troubleshooting

### Nginx 502 Bad Gateway

Check app:

```bash
sudo systemctl status visitor-parking-bot
sudo journalctl -u visitor-parking-bot -n 100 --no-pager
curl http://127.0.0.1:8000/health
```

### HTTPS Certificate Fails

Check DNS:

```bash
dig yourdomain.com
```

Check Nginx:

```bash
sudo nginx -t
```

Retry:

```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

### Chromium Fails To Launch

```bash
cd /opt/visitor-parking-bot/appsrc
sudo .venv/bin/playwright install-deps chromium
sudo -u visitorbot .venv/bin/playwright install chromium
sudo systemctl restart visitor-parking-xvfb
sudo systemctl restart visitor-parking-bot
```

### CAPTCHA Cannot Be Seen

Check Xvfb:

```bash
sudo systemctl status visitor-parking-xvfb
```

Connect with VNC/noVNC through SSH tunnel.

### Scheduler Runs Too Late

Decrease:

```env
SCHEDULER_INTERVAL_SECONDS=300
```

Then:

```bash
sudo systemctl restart visitor-parking-bot
```

## Final Architecture Diagram

```text
                 Internet User
                      |
                      v
              https://yourdomain.com
                      |
                      v
                 AWS Lightsail
                      |
        +-------------+-------------+
        |                           |
        v                           v
      Nginx                  SSH / VNC tunnel
        |                           |
        v                           v
  Gunicorn + Uvicorn          Remote Chromium view
        |
        v
     FastAPI app
        |
        +--> SQLite DB
        |
        +--> APScheduler
        |       |
        |       v
        |   due registrations
        |
        +--> Playwright Chromium on Xvfb :99
        |       |
        |       v
        |   Register2Park website
        |
        +--> screenshots/
        |
        +--> systemd journal logs
```

## Source References

- AWS Lightsail pricing: https://aws.amazon.com/lightsail/pricing/
- AWS public IPv4 pricing: https://aws.amazon.com/vpc/pricing/
- Playwright Python installation/system requirements: https://playwright.dev/python/docs/intro
- Certbot Nginx instructions: https://certbot.eff.org/instructions?ws=nginx&os=snap
