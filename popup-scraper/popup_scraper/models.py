"""Core data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Post:
    """A single Instagram post from a followed artist."""

    media_id: str
    artist_username: str
    caption: str
    image_urls: list[str]
    permalink: str
    taken_at: Optional[datetime] = None


@dataclass
class PopupDetection:
    """Structured result of running a post's image(s) through the vision model."""

    is_popup: bool
    confidence: float
    summary: str
    location: Optional[str] = None
    venue: Optional[str] = None
    city: Optional[str] = None
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    raw: dict = field(default_factory=dict)


@dataclass
class Subscriber:
    """Someone who receives the pop-up text blasts."""

    phone: str
    name: Optional[str] = None
    active: bool = True
    created_at: Optional[datetime] = None
