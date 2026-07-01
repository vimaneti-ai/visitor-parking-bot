"""
In-process runtime status for long-running browser attempts.

This is intentionally lightweight: it lets the local UI show live messages
while a background Playwright attempt is running or paused for manual action.
The durable source of truth remains the registrations and attempts tables.
"""
from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Any

_statuses: dict[int, dict[str, Any]] = {}
_lock = Lock()


def set_runtime_status(
    registration_id: int,
    state: str,
    message: str,
    screenshot_path: str | None = None,
) -> None:
    with _lock:
        _statuses[registration_id] = {
            "registration_id": registration_id,
            "state": state,
            "message": message,
            "screenshot_path": screenshot_path,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }


def get_runtime_status(registration_id: int) -> dict[str, Any]:
    with _lock:
        return _statuses.get(
            registration_id,
            {
                "registration_id": registration_id,
                "state": "idle",
                "message": "No automation attempt is currently running.",
                "screenshot_path": None,
                "updated_at": None,
            },
        ).copy()
