"""Configuration loading from environment variables (and an optional .env)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # optional dependency, only used to load a local .env for convenience
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass


class ConfigError(RuntimeError):
    """Raised when required configuration is missing."""


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(
            f"Missing required environment variable: {name}. "
            "Copy .env.example to .env and fill it in."
        )
    return value


@dataclass
class Config:
    # Instagram
    ig_username: str
    ig_password: str
    ig_session_file: str

    # Vision
    anthropic_api_key: str
    vision_model: str

    # Twilio
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str

    # App
    database_path: str
    artists_file: str
    confidence_threshold: float
    posts_per_artist: int
    poll_interval_seconds: int
    notifier: str  # "twilio" or "console"

    @classmethod
    def from_env(cls) -> "Config":
        """Build config from the environment.

        Only fields needed for the requested command are strictly required, so
        we validate lazily via the `require_*` helpers rather than up front.
        """
        return cls(
            ig_username=os.environ.get("IG_USERNAME", ""),
            ig_password=os.environ.get("IG_PASSWORD", ""),
            ig_session_file=os.environ.get("IG_SESSION_FILE", "./ig_session.json"),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            vision_model=os.environ.get("VISION_MODEL", "claude-sonnet-5"),
            twilio_account_sid=os.environ.get("TWILIO_ACCOUNT_SID", ""),
            twilio_auth_token=os.environ.get("TWILIO_AUTH_TOKEN", ""),
            twilio_from_number=os.environ.get("TWILIO_FROM_NUMBER", ""),
            database_path=os.environ.get("DATABASE_PATH", "./popup_scraper.db"),
            artists_file=os.environ.get("ARTISTS_FILE", "./artists.yaml"),
            confidence_threshold=float(os.environ.get("CONFIDENCE_THRESHOLD", "0.7")),
            posts_per_artist=int(os.environ.get("POSTS_PER_ARTIST", "5")),
            poll_interval_seconds=int(os.environ.get("POLL_INTERVAL_SECONDS", "1800")),
            notifier=os.environ.get("NOTIFIER", "twilio").lower(),
        )

    def require_instagram(self) -> None:
        _require("IG_USERNAME")
        _require("IG_PASSWORD")

    def require_vision(self) -> None:
        _require("ANTHROPIC_API_KEY")

    def require_twilio(self) -> None:
        _require("TWILIO_ACCOUNT_SID")
        _require("TWILIO_AUTH_TOKEN")
        _require("TWILIO_FROM_NUMBER")

    def artists_path(self) -> Path:
        return Path(self.artists_file)
