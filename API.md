# API

The FastAPI app exposes both a local UI and JSON API.

Interactive docs:

```text
http://127.0.0.1:8000/docs
```

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Local browser UI |
| `GET` | `/health` | Health check |
| `POST` | `/registrations` | Create registration and start first attempt |
| `GET` | `/registrations` | List registrations |
| `GET` | `/registrations/{id}` | Get registration with attempts |
| `GET` | `/registrations/{id}/runtime-status` | Get live in-memory automation status |
| `POST` | `/registrations/{id}/cancel` | Cancel future attempts |

## Create Registration

```bash
curl -X POST http://127.0.0.1:8000/registrations \
  -H "Content-Type: application/json" \
  -d '{
    "website_url": "https://www.register2park.com/",
    "apartment_name": "Lakeside Urban Center Apartments",
    "apartment_number": "1234",
    "email": "test@example.com",
    "plate_number": "ABC1234",
    "confirm_plate_number": "ABC1234",
    "plate_state": "TX",
    "vehicle_make": "Toyota",
    "vehicle_model": "Camry",
    "vehicle_year": 2020,
    "vehicle_color": "Black",
    "days": 7
  }'
```

Validation:

- `email` must be valid.
- `plate_number` and `confirm_plate_number` must match.
- `plate_state` must be 2 characters.
- `vehicle_year` must be between 1980 and 2100.
- `days` must be between 1 and 14.

On success, the registration is saved as `PENDING` and the first browser
attempt starts in the background.

## List Registrations

```bash
curl http://127.0.0.1:8000/registrations
```

## Get One Registration

```bash
curl http://127.0.0.1:8000/registrations/1
```

This returns the registration plus all saved attempts.

## Runtime Status

```bash
curl http://127.0.0.1:8000/registrations/1/runtime-status
```

This is live, in-memory status for the currently running automation attempt.
It is useful for UI messages such as:

- `running`
- `captcha_paused`
- `captcha_resumed`
- `success`
- `completed`
- `failed`
- `idle`

Durable history is still stored in `registration_attempts`.

## Cancel Registration

```bash
curl -X POST http://127.0.0.1:8000/registrations/1/cancel
```

Cancel sets:

- `status = CANCELLED`
- `next_registration_at = NULL`

The scheduler will not run future attempts for a cancelled registration.

## Registration Statuses

| Status | Meaning |
| --- | --- |
| `PENDING` | Saved and waiting for first successful registration |
| `ACTIVE` | At least one success; daily re-registration is scheduled |
| `COMPLETED` | Requested number of successful registrations reached |
| `FAILED` | Stopped because of a hard blocker or unrecoverable state |
| `CANCELLED` | User cancelled future attempts |

## Attempt Statuses

| Status | Meaning |
| --- | --- |
| `SUCCESS` | Registration attempt succeeded |
| `FAILED` | Normal automation failure; retry may be scheduled |
| `BLOCKED` | Hard security gate such as login, OTP, or payment wall |
