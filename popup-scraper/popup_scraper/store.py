"""SQLite persistence: post dedup, subscribers, detections, and sent blasts."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from .models import PopupDetection, Subscriber

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_media (
    media_id     TEXT PRIMARY KEY,
    artist       TEXT NOT NULL,
    is_popup     INTEGER NOT NULL DEFAULT 0,
    processed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscribers (
    phone      TEXT PRIMARY KEY,
    name       TEXT,
    active     INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS detections (
    media_id   TEXT PRIMARY KEY,
    artist     TEXT NOT NULL,
    confidence REAL NOT NULL,
    location   TEXT,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    media_id   TEXT PRIMARY KEY,
    recipients INTEGER NOT NULL,
    sent_at    TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    """Thin, dependency-free wrapper over SQLite for the scraper's state."""

    def __init__(self, path: str):
        self.path = path
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # ---- dedup -----------------------------------------------------------
    def has_seen(self, media_id: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM seen_media WHERE media_id = ?", (media_id,)
        )
        return cur.fetchone() is not None

    def mark_seen(self, media_id: str, artist: str, is_popup: bool) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO seen_media (media_id, artist, is_popup, processed_at) "
                "VALUES (?, ?, ?, ?)",
                (media_id, artist, 1 if is_popup else 0, _now()),
            )

    # ---- detections ------------------------------------------------------
    def record_detection(
        self, media_id: str, artist: str, detection: PopupDetection
    ) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO detections "
                "(media_id, artist, confidence, location, payload, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    media_id,
                    artist,
                    detection.confidence,
                    detection.location,
                    json.dumps(detection.__dict__, default=str),
                    _now(),
                ),
            )

    # ---- notifications ---------------------------------------------------
    def was_notified(self, media_id: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM notifications WHERE media_id = ?", (media_id,)
        )
        return cur.fetchone() is not None

    def mark_notified(self, media_id: str, recipients: int) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO notifications (media_id, recipients, sent_at) "
                "VALUES (?, ?, ?)",
                (media_id, recipients, _now()),
            )

    # ---- subscribers -----------------------------------------------------
    def add_subscriber(self, phone: str, name: Optional[str] = None) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO subscribers (phone, name, active, created_at) "
                "VALUES (?, ?, 1, ?) "
                "ON CONFLICT(phone) DO UPDATE SET active = 1, name = COALESCE(excluded.name, name)",
                (phone, name, _now()),
            )

    def remove_subscriber(self, phone: str) -> None:
        """Soft-remove (opt out) so we keep a record and honor STOP requests."""
        with self._tx() as conn:
            conn.execute(
                "UPDATE subscribers SET active = 0 WHERE phone = ?", (phone,)
            )

    def list_subscribers(self, active_only: bool = True) -> list[Subscriber]:
        query = "SELECT phone, name, active, created_at FROM subscribers"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY created_at"
        rows = self._conn.execute(query).fetchall()
        return [
            Subscriber(
                phone=r["phone"],
                name=r["name"],
                active=bool(r["active"]),
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]

    def active_phone_numbers(self) -> list[str]:
        return [s.phone for s in self.list_subscribers(active_only=True)]
