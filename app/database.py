"""
SQLite database setup using SQLAlchemy.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create tables if they do not already exist."""
    from app import models  # noqa: F401  (ensures models are registered)

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns() -> None:
    """Apply small SQLite-only compatibility changes for the local MVP DB."""
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    if "registrations" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("registrations")}
    registration_columns = {
        "apartment_number": "ALTER TABLE registrations ADD COLUMN apartment_number VARCHAR NOT NULL DEFAULT ''",
        "confirm_plate_number": "ALTER TABLE registrations ADD COLUMN confirm_plate_number VARCHAR NOT NULL DEFAULT ''",
        "first_registered_at": "ALTER TABLE registrations ADD COLUMN first_registered_at DATETIME",
        "expires_at": "ALTER TABLE registrations ADD COLUMN expires_at DATETIME",
    }
    with engine.begin() as connection:
        for column_name, statement in registration_columns.items():
            if column_name not in columns:
                connection.execute(text(statement))

    attempt_columns = {column["name"] for column in inspector.get_columns("registration_attempts")}
    if "confirmation_text" not in attempt_columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE registration_attempts ADD COLUMN confirmation_text VARCHAR")
            )


def get_db():
    """FastAPI dependency that yields a DB session and closes it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
