"""
Screenshot retention cleanup.

Debug screenshots can contain vehicle or registration details, so keep them
only long enough to troubleshoot recent automation runs.
"""
from __future__ import annotations

import time
from pathlib import Path

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def cleanup_old_screenshots(
    screenshot_dir: Path | None = None,
    retention_hours: int | None = None,
    current_time: float | None = None,
) -> int:
    """Delete screenshot image files older than the configured retention."""
    target_dir = screenshot_dir or settings.screenshot_path
    retention = (
        retention_hours
        if retention_hours is not None
        else settings.screenshot_retention_hours
    )
    now = current_time if current_time is not None else time.time()
    cutoff = now - (retention * 60 * 60)
    deleted = 0

    if retention <= 0:
        logger.warning("Screenshot cleanup skipped because retention is %s hours", retention)
        return 0

    if not target_dir.exists():
        return 0

    for path in target_dir.iterdir():
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        try:
            if path.stat().st_mtime >= cutoff:
                continue
            path.unlink()
            deleted += 1
            logger.info("Deleted old screenshot: %s", path)
        except FileNotFoundError:
            continue
        except OSError as exc:
            logger.warning("Failed to delete old screenshot %s: %s", path, exc)

    return deleted
