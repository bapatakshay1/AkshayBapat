"""SMS notification layer.

`Notifier` is an abstract interface. `TwilioNotifier` sends real texts;
`ConsoleNotifier` prints them (safe for testing / dry runs).
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Iterable

logger = logging.getLogger(__name__)


class Notifier(ABC):
    @abstractmethod
    def send_blast(self, phone_numbers: Iterable[str], message: str) -> int:
        """Send `message` to each number. Returns the count successfully sent."""


class ConsoleNotifier(Notifier):
    """Prints messages instead of sending them. Useful for local testing."""

    def send_blast(self, phone_numbers: Iterable[str], message: str) -> int:
        numbers = list(phone_numbers)
        print("=" * 60)
        print(f"[DRY RUN] Would text {len(numbers)} subscriber(s):")
        print(message)
        print(f"Recipients: {', '.join(numbers) if numbers else '(none)'}")
        print("=" * 60)
        return len(numbers)


class TwilioNotifier(Notifier):
    """Sends texts via Twilio."""

    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self._from = from_number
        from twilio.rest import Client  # lazy import

        self._client = Client(account_sid, auth_token)

    def send_blast(self, phone_numbers: Iterable[str], message: str) -> int:
        sent = 0
        for number in phone_numbers:
            try:
                self._client.messages.create(
                    to=number, from_=self._from, body=message
                )
                sent += 1
            except Exception as exc:  # pragma: no cover - network path
                logger.warning("Failed to text %s: %s", number, exc)
        return sent
