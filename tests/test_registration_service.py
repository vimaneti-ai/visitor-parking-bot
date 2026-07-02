"""
Basic tests for registration_service.py.

These tests use an isolated in-memory SQLite database and monkeypatch the
Playwright automation call so no real browser or network access is needed.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.schemas import RegistrationCreate
from app.services import registration_service as svc


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _sample_payload(**overrides) -> RegistrationCreate:
    data = dict(
        website_url="https://example.com/register",
        apartment_name="Sample Apartments",
        apartment_number="1234",
        email="test@example.com",
        plate_number="ABC1234",
        confirm_plate_number="ABC1234",
        plate_state="tx",
        vehicle_make="Toyota",
        vehicle_model="Camry",
        vehicle_year=2020,
        vehicle_color="Black",
        days=3,
    )
    data.update(overrides)
    return RegistrationCreate(**data)


def test_create_registration_starts_pending_for_immediate_attempt(db_session):
    registration = svc.create_registration(db_session, _sample_payload())

    assert registration.id is not None
    assert registration.status == "PENDING"
    assert registration.registration_count == 0
    assert registration.plate_state == "TX"
    assert registration.confirm_plate_number == "ABC1234"
    assert registration.next_registration_at is not None
    assert registration.first_registered_at is None
    assert registration.expires_at is None


def test_run_attempt_success_increments_count_and_reschedules(db_session, monkeypatch):
    registration = svc.create_registration(db_session, _sample_payload(days=3))

    class FakeResult:
        success = True
        message = "ok"
        screenshot_path = "/tmp/fake.png"
        confirmation_text = "confirmation ok"

    monkeypatch.setattr(svc, "run_registration", lambda automation_input, **kwargs: FakeResult())

    before = datetime.utcnow()
    now = before
    svc.run_attempt_for_registration(db_session, registration, now)
    after = datetime.utcnow()

    assert registration.registration_count == 1
    assert registration.status == "ACTIVE"
    assert registration.first_registered_at is not None
    assert registration.last_registered_at is not None
    assert before <= registration.first_registered_at <= after
    assert registration.last_registered_at == registration.first_registered_at
    assert registration.expires_at == registration.last_registered_at + timedelta(hours=24)
    assert registration.next_registration_at == registration.expires_at
    assert len(registration.attempts) == 1
    assert registration.attempts[0].status == "SUCCESS"
    assert registration.attempts[0].confirmation_text == "confirmation ok"


def test_run_attempt_completes_after_final_day(db_session, monkeypatch):
    registration = svc.create_registration(db_session, _sample_payload(days=1))

    class FakeResult:
        success = True
        message = "ok"
        screenshot_path = None
        confirmation_text = None

    monkeypatch.setattr(svc, "run_registration", lambda automation_input, **kwargs: FakeResult())

    now = datetime.utcnow()
    svc.run_attempt_for_registration(db_session, registration, now)

    assert registration.registration_count == 1
    assert registration.status == "COMPLETED"
    assert registration.next_registration_at is None
    assert registration.expires_at == registration.last_registered_at + timedelta(hours=24)


def test_run_attempt_failure_retries_later(db_session, monkeypatch):
    registration = svc.create_registration(db_session, _sample_payload(days=3))

    class FakeResult:
        success = False
        message = "no success text found"
        screenshot_path = "/tmp/fail.png"
        confirmation_text = None

    monkeypatch.setattr(svc, "run_registration", lambda automation_input, **kwargs: FakeResult())

    now = datetime.utcnow()
    svc.run_attempt_for_registration(db_session, registration, now)

    assert registration.registration_count == 0
    assert registration.status == "PENDING"
    assert registration.next_registration_at is not None
    assert registration.next_registration_at > now
    assert registration.attempts[0].status == "FAILED"


def test_email_submitted_failure_pauses_automatic_retries(db_session, monkeypatch):
    registration = svc.create_registration(db_session, _sample_payload(days=3))

    class FakeResult:
        success = False
        message = "Email confirmation was submitted, but final success could not be verified."
        screenshot_path = "/tmp/email-submitted.png"
        confirmation_text = None
        retryable = False
        email_submitted = True

    monkeypatch.setattr(svc, "run_registration", lambda automation_input, **kwargs: FakeResult())

    svc.run_attempt_for_registration(db_session, registration, datetime.utcnow())

    assert registration.registration_count == 0
    assert registration.status == "ACTION_REQUIRED"
    assert registration.next_registration_at is None
    assert registration.attempts[0].status == "FAILED"
    assert "Email confirmation was submitted" in registration.attempts[0].message


def test_run_attempt_blocked_marks_failed_and_stops(db_session, monkeypatch):
    registration = svc.create_registration(db_session, _sample_payload(days=3))

    def raise_blocked(automation_input, **kwargs):
        raise svc.BlockedByGateError("CAPTCHA detected")

    monkeypatch.setattr(svc, "run_registration", raise_blocked)

    now = datetime.utcnow()
    svc.run_attempt_for_registration(db_session, registration, now)

    assert registration.status == "FAILED"
    assert registration.next_registration_at is None
    assert registration.attempts[0].status == "BLOCKED"


def test_get_due_registrations_filters_by_time_and_status(db_session):
    reg = svc.create_registration(db_session, _sample_payload(days=2))

    now = datetime.utcnow()
    # Not due yet.
    reg.next_registration_at = now + timedelta(hours=1)
    db_session.commit()
    assert svc.get_due_registrations(db_session, now) == []

    # Due now.
    reg.next_registration_at = now - timedelta(minutes=1)
    db_session.commit()
    due = svc.get_due_registrations(db_session, now)
    assert len(due) == 1
    assert due[0].id == reg.id


def test_cancel_registration_stops_future_attempts(db_session):
    reg = svc.create_registration(db_session, _sample_payload(days=2))

    cancelled = svc.cancel_registration(db_session, reg.id)

    assert cancelled is not None
    assert cancelled.status == "CANCELLED"
    assert cancelled.next_registration_at is None
