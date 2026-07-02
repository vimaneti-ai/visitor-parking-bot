# Database

The app uses SQLite through SQLAlchemy.

Default database:

```text
/Users/vinod/Projects/visitor-parking-bot/visitor_parking.db
```

Configured by:

```env
DATABASE_URL=sqlite:///./visitor_parking.db
```

## Open The Database

From the project root:

```bash
cd /Users/vinod/Projects/visitor-parking-bot
sqlite3 visitor_parking.db
```

From anywhere:

```bash
sqlite3 /Users/vinod/Projects/visitor-parking-bot/visitor_parking.db
```

If you run `sqlite3 visitor_parking.db` from your home folder, SQLite will
create/open `~/visitor_parking.db`, which will not contain the project tables.

## Open The AWS Production Database

On AWS, the production `.env` should point to:

```env
DATABASE_URL=sqlite:////opt/visitor-parking-bot/data/visitor_parking.db
```

Because the app runs as `visitorbot`, inspect the production database with
`sudo`:

```bash
sudo sqlite3 /opt/visitor-parking-bot/data/visitor_parking.db
```

Then run one SQLite command per line:

```sql
.tables
```

```sql
.headers on
```

```sql
.mode column
```

```sql
SELECT id, apartment_number, plate_number, email, status,
       registration_count, next_registration_at
FROM registrations;
```

```sql
SELECT id, registration_id, attempted_at, status, message
FROM registration_attempts
ORDER BY attempted_at DESC;
```

Exit:

```sql
.quit
```

If you see `unable to open database file`, check ownership and existence:

```bash
sudo ls -la /opt/visitor-parking-bot/data
sudo cat /opt/visitor-parking-bot/appsrc/.env
sudo systemctl restart visitor-parking-bot
```

## Tables

```sql
.tables
```

Expected:

```text
registration_attempts  registrations
```

## Registrations Table

Stores one requested multi-day registration.

Important columns:

- `id`
- `website_url`
- `apartment_name`
- `apartment_number`
- `email`
- `plate_number`
- `confirm_plate_number`
- `plate_state`
- `vehicle_make`
- `vehicle_model`
- `vehicle_year`
- `vehicle_color`
- `days`
- `status`
- `registration_count`
- `first_registered_at`
- `last_registered_at`
- `next_registration_at`
- `expires_at`
- `created_at`
- `updated_at`

Useful query:

```sql
SELECT id, apartment_name, apartment_number, plate_number, status,
       registration_count, first_registered_at, last_registered_at,
       expires_at, next_registration_at
FROM registrations
ORDER BY created_at DESC;
```

## Registration Attempts Table

Stores each browser automation attempt.

Important columns:

- `id`
- `registration_id`
- `attempted_at`
- `status`
- `message`
- `screenshot_path`
- `confirmation_text`

Useful query:

```sql
SELECT registration_id, attempted_at, status, message,
       screenshot_path, confirmation_text
FROM registration_attempts
ORDER BY attempted_at DESC;
```

## Schedule Fields

- `first_registered_at`: actual timestamp of the first successful registration.
- `last_registered_at`: actual timestamp of the most recent successful registration.
- `expires_at`: `last_registered_at + 24 hours`.
- `next_registration_at`: when the scheduler should run the next attempt.

The app does not use the original submit time as the daily anchor unless the
first registration succeeds at that exact time. The actual success timestamp is
the source of truth.

## Action Required Status

`ACTION_REQUIRED` means automation paused future retries. The main case is:

1. Register2Park email confirmation was submitted.
2. The bot could not verify final success text afterward.
3. Automatic retries were stopped to avoid sending repeated confirmation
   emails every scheduler cycle.

Inspect these rows with:

```sql
SELECT id, status, next_registration_at
FROM registrations
WHERE status = 'ACTION_REQUIRED';
```

Use the UI `Retry now` button or `POST /registrations/{id}/retry` only when you
intentionally want another attempt/email.

## Schema Creation

`app.database.init_db()` runs during FastAPI startup.

The project uses `create_all()` plus small SQLite compatibility column checks.
It does not currently use Alembic migrations.
