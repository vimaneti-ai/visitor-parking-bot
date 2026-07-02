from __future__ import annotations

import os

from app.services.screenshot_cleanup import cleanup_old_screenshots


def test_cleanup_old_screenshots_deletes_images_older_than_retention(tmp_path):
    now = 1_700_000_000.0
    old_png = tmp_path / "old.png"
    old_jpg = tmp_path / "old.jpg"
    recent_png = tmp_path / "recent.png"
    note = tmp_path / "note.txt"

    for path in (old_png, old_jpg, recent_png, note):
        path.write_text("x")

    os.utime(old_png, (now - (25 * 60 * 60), now - (25 * 60 * 60)))
    os.utime(old_jpg, (now - (26 * 60 * 60), now - (26 * 60 * 60)))
    os.utime(recent_png, (now - (23 * 60 * 60), now - (23 * 60 * 60)))
    os.utime(note, (now - (30 * 60 * 60), now - (30 * 60 * 60)))

    deleted = cleanup_old_screenshots(tmp_path, retention_hours=24, current_time=now)

    assert deleted == 2
    assert not old_png.exists()
    assert not old_jpg.exists()
    assert recent_png.exists()
    assert note.exists()


def test_cleanup_old_screenshots_skips_missing_directory(tmp_path):
    deleted = cleanup_old_screenshots(tmp_path / "missing", retention_hours=24)

    assert deleted == 0
