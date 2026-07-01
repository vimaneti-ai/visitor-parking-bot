"""
FastAPI application entrypoint.

Run locally with:
    uvicorn app.main:app --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.models import Registration
from app.scheduler import start_scheduler, stop_scheduler
from app.schemas import RegistrationCreate, RegistrationDetailOut, RegistrationOut
from app.services.registration_service import (
    cancel_registration,
    create_registration,
    process_registration_by_id,
)
from app.services.runtime_status import get_runtime_status
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    logger.info("Application startup complete")
    yield
    stop_scheduler()
    logger.info("Application shutdown complete")


app = FastAPI(title="Visitor Parking Bot", version="0.1.0", lifespan=lifespan)
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
def ui() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/registrations", response_model=RegistrationOut, status_code=201)
def create_registration_endpoint(
    payload: RegistrationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Registration:
    registration = create_registration(db, payload)
    background_tasks.add_task(process_registration_by_id, registration.id)
    return registration


@app.get("/registrations", response_model=list[RegistrationOut])
def list_registrations(db: Session = Depends(get_db)) -> list[Registration]:
    return db.query(Registration).order_by(Registration.created_at.desc()).all()


@app.get("/registrations/{registration_id}", response_model=RegistrationDetailOut)
def get_registration(registration_id: int, db: Session = Depends(get_db)) -> Registration:
    registration = db.get(Registration, registration_id)
    if registration is None:
        raise HTTPException(status_code=404, detail="Registration not found")
    return registration


@app.get("/registrations/{registration_id}/runtime-status")
def get_registration_runtime_status(registration_id: int) -> dict:
    return get_runtime_status(registration_id)


@app.post("/registrations/{registration_id}/cancel", response_model=RegistrationOut)
def cancel_registration_endpoint(
    registration_id: int, db: Session = Depends(get_db)
) -> Registration:
    registration = cancel_registration(db, registration_id)
    if registration is None:
        raise HTTPException(status_code=404, detail="Registration not found")
    return registration
