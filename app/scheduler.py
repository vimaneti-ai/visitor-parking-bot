"""
APScheduler setup: runs a job every N seconds (default 60 for the MVP) that
checks for due registrations and executes them.
"""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database import SessionLocal
from app.services.registration_service import process_due_registrations
from app.utils.logger import get_logger

logger = get_logger(__name__)

scheduler = BackgroundScheduler()


def _job() -> None:
    db = SessionLocal()
    try:
        count = process_due_registrations(db)
        if count:
            logger.info("Processed %s due registration(s)", count)
    except Exception:  # noqa: BLE001
        logger.exception("Error while processing due registrations")
    finally:
        db.close()


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        _job,
        "interval",
        seconds=settings.scheduler_interval_seconds,
        id="process_due_registrations",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started, checking every %s seconds", settings.scheduler_interval_seconds
    )


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
