"""Orchestration: poll artists -> analyze images -> blast subscribers."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from .config import Config
from .instagram import InstagramSource
from .models import PopupDetection, Post
from .notifier import Notifier
from .store import Store
from .vision import VisionAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class RunStats:
    posts_checked: int = 0
    new_posts: int = 0
    popups_found: int = 0
    blasts_sent: int = 0


def compose_message(post: Post, detection: PopupDetection) -> str:
    """Build the SMS body a subscriber receives."""
    artist = f"@{post.artist_username}"
    where = detection.location or detection.venue or "location in the post"
    when = detection.starts_at or ""
    parts = [f"🎨 Pop-up alert! {artist} is hosting a pop-up."]
    if detection.summary:
        parts.append(detection.summary)
    parts.append(f"📍 {where}")
    if when:
        parts.append(f"🕒 {when}")
    parts.append(post.permalink)
    parts.append("Reply STOP to unsubscribe.")
    return "\n".join(parts)


class Pipeline:
    def __init__(
        self,
        config: Config,
        source: InstagramSource,
        analyzer: VisionAnalyzer,
        notifier: Notifier,
        store: Store,
    ):
        self.config = config
        self.source = source
        self.analyzer = analyzer
        self.notifier = notifier
        self.store = store

    def run_once(self, artists: list[str]) -> RunStats:
        stats = RunStats()
        for username in artists:
            posts = self.source.fetch_recent_posts(
                username, self.config.posts_per_artist
            )
            for post in posts:
                stats.posts_checked += 1
                if self.store.has_seen(post.media_id):
                    continue
                stats.new_posts += 1
                self._process_post(post, stats)
        logger.info(
            "Run complete: %d checked, %d new, %d pop-ups, %d blasts",
            stats.posts_checked,
            stats.new_posts,
            stats.popups_found,
            stats.blasts_sent,
        )
        return stats

    def _process_post(self, post: Post, stats: RunStats) -> None:
        try:
            detection = self.analyzer.analyze(post)
        except Exception as exc:  # pragma: no cover - network path
            logger.exception("Vision analysis failed for %s: %s", post.media_id, exc)
            return

        is_popup = (
            detection.is_popup
            and detection.confidence >= self.config.confidence_threshold
        )
        # Record everything, then mark seen so we never reprocess this post.
        self.store.record_detection(post.media_id, post.artist_username, detection)
        self.store.mark_seen(post.media_id, post.artist_username, is_popup)

        if not is_popup:
            return

        stats.popups_found += 1
        logger.info(
            "Pop-up detected for @%s (%.2f): %s",
            post.artist_username,
            detection.confidence,
            detection.location or detection.venue or "unknown location",
        )

        if self.store.was_notified(post.media_id):
            return
        recipients = self.store.active_phone_numbers()
        if not recipients:
            logger.info("No active subscribers; skipping blast.")
            self.store.mark_notified(post.media_id, 0)
            return

        message = compose_message(post, detection)
        sent = self.notifier.send_blast(recipients, message)
        self.store.mark_notified(post.media_id, sent)
        stats.blasts_sent += sent

    def watch(self, artists: list[str]) -> None:
        """Poll forever on an interval."""
        interval = self.config.poll_interval_seconds
        logger.info("Watching %d artists every %ds.", len(artists), interval)
        while True:
            try:
                self.run_once(artists)
            except Exception as exc:  # pragma: no cover - defensive loop
                logger.exception("Run failed, continuing: %s", exc)
            time.sleep(interval)
