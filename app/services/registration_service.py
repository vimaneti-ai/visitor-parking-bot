"""
Registration business logic: creating registrations, and running/recording
scheduled attempts. Kept separate from the API layer and the scheduler so
both can share the same logic and so it is easy to unit test.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from threading import Lock

from sqlalchemy.orm import Session

from app.automation.register2park_bot import (
    BlockedByGateError,
    RegistrationInput,
    run_registration,
)
from app.config import settings
from app.models import AttemptStatus, Registration, RegistrationAttempt, RegistrationStatus
from app.schemas import RegistrationCreate
from app.services.runtime_status import set_runtime_status
from app.utils.logger import get_logger

logger = get_logger(__name__)

_running_attempt_ids: set[int] = set()
_running_attempt_ids_lock = Lock()


def _try_mark_attempt_running(registration_id: int) -> bool:
    with _running_attempt_ids_lock:
        if registration_id in _running_attempt_ids:
            return False
        _running_attempt_ids.add(registration_id)
        return True


def _clear_attempt_running(registration_id: int) -> None:
    with _running_attempt_ids_lock:
        _running_attempt_ids.discard(registration_id)


def create_registration(db: Session, payload: RegistrationCreate) -> Registration:
    """Create a pending registration record for immediate first attempt."""
    now = datetime.utcnow()

    registration = Registration(
        website_url=payload.website_url,
        apartment_name=payload.apartment_name,
        apartment_number=payload.apartment_number,
        email=payload.email,
        plate_number=payload.plate_number,
        confirm_plate_number=payload.confirm_plate_number,
        plate_state=payload.plate_state,
        vehicle_make=payload.vehicle_make,
        vehicle_model=payload.vehicle_model,
        vehicle_year=payload.vehicle_year,
        vehicle_color=payload.vehicle_color,
        start_date=now,
        end_date=now + timedelta(days=payload.days),
        days=payload.days,
        preferred_registration_time="",
        status=RegistrationStatus.PENDING,
        registration_count=0,
        next_registration_at=now,
    )
    db.add(registration)
    db.commit()
    db.refresh(registration)
    logger.info(
        "Created pending registration id=%s apartment=%s days=%s",
        registration.id,
        registration.apartment_name,
        registration.days,
    )
    return registration


def get_due_registrations(db: Session, now: datetime) -> list[Registration]:
    return (
        db.query(Registration)
        .filter(
            Registration.status.in_([RegistrationStatus.PENDING, RegistrationStatus.ACTIVE]),
            Registration.next_registration_at.isnot(None),
            Registration.next_registration_at <= now,
        )
        .all()
    )


def run_attempt_for_registration(db: Session, registration: Registration, now: datetime) -> None:
    """
    Execute one automation attempt for a registration and update the
    registration + attempts table according to the outcome.
    """
    db.refresh(registration)
    if registration.status in [
        RegistrationStatus.CANCELLED,
        RegistrationStatus.COMPLETED,
        RegistrationStatus.FAILED,
    ]:
        logger.info("Registration id=%s is %s; skipping attempt", registration.id, registration.status)
        return

    if not _try_mark_attempt_running(registration.id):
        logger.info("Registration id=%s already has an attempt running; skipping", registration.id)
        return

    logger.info("Running attempt for registration id=%s", registration.id)
    set_runtime_status(
        registration.id,
        "running",
        "Automation is running.",
    )

    try:
        automation_input = RegistrationInput(
            website_url=registration.website_url,
            apartment_name=registration.apartment_name,
            apartment_number=registration.apartment_number,
            email=registration.email,
            plate_number=registration.plate_number,
            plate_state=registration.plate_state,
            vehicle_make=registration.vehicle_make,
            vehicle_model=registration.vehicle_model,
            vehicle_year=registration.vehicle_year,
            vehicle_color=registration.vehicle_color,
        )

        try:
            result = run_registration(
                automation_input,
                event_callback=lambda state, message, screenshot_path=None: set_runtime_status(
                    registration.id,
                    state,
                    message,
                    screenshot_path,
                ),
            )
        except BlockedByGateError as exc:
            attempt = RegistrationAttempt(
                registration_id=registration.id,
                attempted_at=datetime.utcnow(),
                status=AttemptStatus.BLOCKED,
                message=str(exc),
                screenshot_path=getattr(exc, "screenshot_path", None),
            )
            db.add(attempt)
            registration.status = RegistrationStatus.FAILED
            registration.next_registration_at = None
            db.commit()
            logger.error(
                "Registration id=%s blocked by gate, marking FAILED: %s", registration.id, exc
            )
            set_runtime_status(
                registration.id,
                "failed",
                str(exc),
                getattr(exc, "screenshot_path", None),
            )
            return

        completed_at = datetime.utcnow()
        confirmation_text = getattr(result, "confirmation_text", None)

        if result.success:
            attempt = RegistrationAttempt(
                registration_id=registration.id,
                attempted_at=completed_at,
                status=AttemptStatus.SUCCESS,
                message=result.message,
                screenshot_path=result.screenshot_path,
                confirmation_text=confirmation_text or result.message,
            )
            db.add(attempt)

            registration.registration_count += 1
            if registration.first_registered_at is None:
                registration.first_registered_at = completed_at
            registration.last_registered_at = completed_at
            registration.expires_at = completed_at + timedelta(hours=24)

            if registration.registration_count >= registration.days:
                registration.status = RegistrationStatus.COMPLETED
                registration.next_registration_at = None
                logger.info(
                    "Registration id=%s reached %s/%s days, marking COMPLETED",
                    registration.id,
                    registration.registration_count,
                    registration.days,
                )
                set_runtime_status(
                    registration.id,
                    "completed",
                    "Registration completed successfully.",
                    result.screenshot_path,
                )
            else:
                registration.status = RegistrationStatus.ACTIVE
                registration.next_registration_at = registration.expires_at
                set_runtime_status(
                    registration.id,
                    "success",
                    "Registration completed successfully. Next daily registration is scheduled.",
                    result.screenshot_path,
                )
        else:
            attempt = RegistrationAttempt(
                registration_id=registration.id,
                attempted_at=completed_at,
                status=AttemptStatus.FAILED,
                message=result.message,
                screenshot_path=result.screenshot_path,
                confirmation_text=confirmation_text,
            )
            db.add(attempt)
            registration.next_registration_at = completed_at + timedelta(
                minutes=settings.retry_delay_minutes
            )
            if registration.status != RegistrationStatus.ACTIVE:
                registration.status = RegistrationStatus.PENDING
            logger.warning(
                "Registration id=%s attempt failed, retrying at %s",
                registration.id,
                registration.next_registration_at,
            )
            set_runtime_status(
                registration.id,
                "failed",
                result.message,
                result.screenshot_path,
            )

        db.commit()
    finally:
        _clear_attempt_running(registration.id)


def process_registration_by_id(registration_id: int) -> None:
    """Run one registration attempt in a fresh session for background tasks."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        registration = db.get(Registration, registration_id)
        if registration is None:
            logger.warning("Registration id=%s not found for background attempt", registration_id)
            return
        if registration.status in [RegistrationStatus.CANCELLED, RegistrationStatus.COMPLETED]:
            logger.info("Registration id=%s is %s; skipping attempt", registration.id, registration.status)
            return
        run_attempt_for_registration(db, registration, datetime.utcnow())
    finally:
        db.close()


def cancel_registration(db: Session, registration_id: int) -> Registration | None:
    registration = db.get(Registration, registration_id)
    if registration is None:
        return None
    registration.status = RegistrationStatus.CANCELLED
    registration.next_registration_at = None
    db.commit()
    db.refresh(registration)
    logger.info("Cancelled registration id=%s", registration.id)
    return registration


def process_due_registrations(db: Session) -> int:
    """Find and run all due registrations. Returns the number processed."""
    now = datetime.utcnow()
    due = get_due_registrations(db, now)
    for registration in due:
        run_attempt_for_registration(db, registration, now)
    return len(due)
