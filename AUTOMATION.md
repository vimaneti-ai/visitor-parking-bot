# Automation

The Playwright automation lives in:

```text
app/automation/register2park_bot.py
```

It uses Chromium and runs headed by default so you can watch the flow.

## Register2Park Flow

The automation is split into focused functions:

- `open_homepage()`
- `click_register_vehicle()`
- `select_property()`
- `choose_visitor_parking()`
- `fill_vehicle_information()`
- `submit_vehicle_information()`
- `enter_email()`
- `verify_registration_success()`

High-level flow:

1. Open Register2Park.
2. Click `Register Vehicle`.
3. Search for `Lakeside Urban Center Apartments`.
4. Click matching property confirmation if Register2Park shows it.
5. Choose visitor parking.
6. Fill apartment number and vehicle details.
7. Submit vehicle details.
8. Pause for CAPTCHA if shown.
9. If approval page appears, click `E-Mail Confirmation`.
10. Enter the provided email and submit.
11. Detect final approval/confirmation.

## Duplicate Email Protection

If the email confirmation step completes but the automation cannot verify a
final success page afterward, the registration is moved to `ACTION_REQUIRED`.

That means:

- the attempt is recorded as `FAILED`
- `next_registration_at` is cleared
- the scheduler will not retry automatically
- another confirmation email is not sent every scheduler cycle
- the UI shows a `Retry now` button for a deliberate manual retry

This protects against repeated confirmation emails when Register2Park accepts
the email submission but does not show a success marker the bot recognizes.

## CAPTCHA Handling

The app does not bypass CAPTCHA.

If CAPTCHA appears:

1. Automation saves a screenshot.
2. Browser remains open.
3. Runtime status changes to `captcha_paused`.
4. UI displays a manual completion message.
5. You solve CAPTCHA in the open browser.
6. Automation detects CAPTCHA completion or registration content.
7. Runtime status changes to `captcha_resumed`.
8. Automation continues from the same page.

Timeout is controlled by:

```env
MANUAL_CAPTCHA_TIMEOUT_SECONDS=300
```

## Hard Blockers

The automation stops on gates that should not be bypassed:

- Login page
- OTP or verification-code page
- Payment page
- Security checks other than manual CAPTCHA
- Unexpected browser dialog

These are recorded as failed or blocked attempts with screenshot paths.

## Screenshots

Screenshots are saved to:

```text
screenshots/
```

Examples:

- `step_1_homepage_...png`
- `step_3_property_selected_...png`
- `before_email_captcha_manual_required_...png`
- `step_7_confirmation_...png`
- `email_missing_...png`

Screenshots are gitignored.

## Manual CLI Run

Use this to test selectors without the API/scheduler:

```bash
source .venv/bin/activate
python -m app.automation.register2park_bot \
  --url "https://www.register2park.com/" \
  --property "Lakeside Urban Center Apartments" \
  --apartment "1234" \
  --email "test@example.com" \
  --plate "ABC1234" \
  --state "TX" \
  --make "Toyota" \
  --model "Camry" \
  --year 2020 \
  --color "Black"
```

## Selectors Most Likely To Change

If Register2Park changes its UI, check:

- `Register Vehicle` button/link
- Property search input
- Matching property `Select` button
- Visitor parking choice
- Apartment/unit field
- Vehicle make/model fields
- Plate and confirm plate fields
- State selector
- `Next`, `Continue`, `Submit`, `Send`, or email buttons
- Approval and confirmation text

The code prefers Playwright role, label, placeholder, text, id, and name
selectors, with CSS fallbacks where useful.
