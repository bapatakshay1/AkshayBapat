"""Instagram access layer.

`InstagramSource` is an abstract interface so the rest of the app never depends
on *how* posts are fetched. `InstagrapiSource` is the default implementation,
built on the unofficial private-API client `instagrapi`.

WARNING: Driving a personal Instagram account through the private API violates
Instagram's Terms of Service and can get the account rate-limited or banned.
Use a dedicated account, keep polling gentle, and treat this layer as swappable.
"""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Iterable

from .models import Post

logger = logging.getLogger(__name__)


class InstagramSource(ABC):
    """Abstract source of Instagram posts + the ability to follow artists."""

    @abstractmethod
    def login(self) -> None:
        ...

    @abstractmethod
    def follow_artists(self, usernames: Iterable[str]) -> dict[str, bool]:
        """Follow each username. Returns {username: success}."""

    @abstractmethod
    def fetch_recent_posts(self, username: str, amount: int) -> list[Post]:
        ...


class InstagrapiSource(InstagramSource):
    """Default implementation using the `instagrapi` private API client."""

    def __init__(self, username: str, password: str, session_file: str):
        self._username = username
        self._password = password
        self._session_file = session_file
        self._client = None  # lazy import so the dependency is optional in tests

    def _get_client(self):
        if self._client is not None:
            return self._client
        from instagrapi import Client  # imported lazily

        self._client = Client()
        return self._client

    def login(self) -> None:
        client = self._get_client()
        # Reuse a cached session when possible to avoid repeated logins, which
        # Instagram treats as suspicious.
        if os.path.exists(self._session_file):
            try:
                client.load_settings(self._session_file)
                client.login(self._username, self._password)
                client.get_timeline_feed()  # validates the session
                logger.info("Reused existing Instagram session.")
                return
            except Exception as exc:  # pragma: no cover - network path
                logger.warning("Cached session invalid (%s); logging in fresh.", exc)

        client.login(self._username, self._password)
        client.dump_settings(self._session_file)
        logger.info("Logged in and saved session to %s", self._session_file)

    def follow_artists(self, usernames: Iterable[str]) -> dict[str, bool]:
        client = self._get_client()
        results: dict[str, bool] = {}
        for username in usernames:
            try:
                user_id = client.user_id_from_username(username)
                results[username] = bool(client.user_follow(user_id))
                logger.info("Followed %s", username)
            except Exception as exc:  # pragma: no cover - network path
                logger.warning("Failed to follow %s: %s", username, exc)
                results[username] = False
        return results

    def fetch_recent_posts(self, username: str, amount: int) -> list[Post]:
        client = self._get_client()
        try:
            user_id = client.user_id_from_username(username)
            medias = client.user_medias(user_id, amount=amount)
        except Exception as exc:  # pragma: no cover - network path
            logger.warning("Failed to fetch posts for %s: %s", username, exc)
            return []

        posts: list[Post] = []
        for media in medias:
            posts.append(
                Post(
                    media_id=str(media.pk),
                    artist_username=username,
                    caption=media.caption_text or "",
                    image_urls=_image_urls(media),
                    permalink=f"https://www.instagram.com/p/{media.code}/",
                    taken_at=getattr(media, "taken_at", None),
                )
            )
        return posts


def _image_urls(media) -> list[str]:
    """Extract still-image URLs from an instagrapi media object.

    Handles single photos, videos (thumbnail), and albums (carousels).
    """
    urls: list[str] = []
    resources = getattr(media, "resources", None) or []
    if resources:
        for res in resources:
            url = getattr(res, "thumbnail_url", None)
            if url:
                urls.append(str(url))
    else:
        url = getattr(media, "thumbnail_url", None)
        if url:
            urls.append(str(url))
    return urls
