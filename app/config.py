"""
Application configuration.

All sensitive or environment-specific values are loaded from environment
variables (via a local .env file, which is gitignored). Nothing here should
contain real personal data - copy .env.example to .env and fill it in
locally.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./visitor_parking.db"
    screenshot_dir: str = "./screenshots"
    screenshot_retention_hours: int = 24

    register2park_url: str = "https://www.register2park.com/"
    register2park_property_name: str = "Lakeside Urban Center Apartments"

    playwright_headless: bool = False
    playwright_timeout_ms: int = 30000
    manual_captcha_timeout_seconds: int = 300

    scheduler_interval_seconds: int = 7200
    screenshot_cleanup_interval_seconds: int = 3600
    retry_delay_minutes: int = 30

    log_level: str = "INFO"

    # Optional local defaults - fine to leave blank. Real values should be
    # supplied per-request via the API, not hardcoded here.
    default_email: str = ""
    default_plate_number: str = ""
    default_plate_state: str = ""

    @property
    def screenshot_path(self) -> Path:
        path = Path(self.screenshot_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
