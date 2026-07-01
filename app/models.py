"""
SQLAlchemy ORM models.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RegistrationStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AttemptStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"  # e.g. CAPTCHA / OTP / login / payment wall detected


class Registration(Base):
    __tablename__ = "registrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    website_url: Mapped[str] = mapped_column(String, nullable=False)
    apartment_name: Mapped[str] = mapped_column(String, nullable=False)
    apartment_number: Mapped[str] = mapped_column(String, nullable=False, default="")
    email: Mapped[str] = mapped_column(String, nullable=False)

    plate_number: Mapped[str] = mapped_column(String, nullable=False)
    confirm_plate_number: Mapped[str] = mapped_column(String, nullable=False, default="")
    plate_state: Mapped[str] = mapped_column(String, nullable=False)
    vehicle_make: Mapped[str] = mapped_column(String, nullable=False)
    vehicle_model: Mapped[str] = mapped_column(String, nullable=False)
    vehicle_year: Mapped[int] = mapped_column(Integer, nullable=False)
    vehicle_color: Mapped[str] = mapped_column(String, nullable=False)

    # Legacy scheduling fields kept nullable for compatibility with older rows.
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    preferred_registration_time: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(
        Enum(RegistrationStatus), nullable=False, default=RegistrationStatus.PENDING
    )
    registration_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    first_registered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_registered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_registration_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    attempts: Mapped[list["RegistrationAttempt"]] = relationship(
        back_populates="registration", cascade="all, delete-orphan"
    )


class RegistrationAttempt(Base):
    __tablename__ = "registration_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    registration_id: Mapped[int] = mapped_column(ForeignKey("registrations.id"), nullable=False)

    attempted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(Enum(AttemptStatus), nullable=False)
    message: Mapped[str | None] = mapped_column(String, nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(String, nullable=True)
    confirmation_text: Mapped[str | None] = mapped_column(String, nullable=True)

    registration: Mapped["Registration"] = relationship(back_populates="attempts")
