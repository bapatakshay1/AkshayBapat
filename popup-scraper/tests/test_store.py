import os
import tempfile

from popup_scraper.models import PopupDetection
from popup_scraper.store import Store


def _store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return Store(path), path


def test_dedup():
    store, path = _store()
    try:
        assert not store.has_seen("m1")
        store.mark_seen("m1", "artist", is_popup=True)
        assert store.has_seen("m1")
    finally:
        store.close()
        os.remove(path)


def test_subscribers_add_remove_list():
    store, path = _store()
    try:
        store.add_subscriber("+15551110000", name="Ada")
        store.add_subscriber("+15552220000")
        assert set(store.active_phone_numbers()) == {"+15551110000", "+15552220000"}

        store.remove_subscriber("+15552220000")
        assert store.active_phone_numbers() == ["+15551110000"]

        # Re-adding an opted-out number reactivates it.
        store.add_subscriber("+15552220000")
        assert len(store.active_phone_numbers()) == 2

        all_subs = store.list_subscribers(active_only=False)
        assert len(all_subs) == 2
    finally:
        store.close()
        os.remove(path)


def test_notifications_recorded_once():
    store, path = _store()
    try:
        assert not store.was_notified("m1")
        store.mark_notified("m1", recipients=3)
        assert store.was_notified("m1")
    finally:
        store.close()
        os.remove(path)


def test_record_detection():
    store, path = _store()
    try:
        det = PopupDetection(
            is_popup=True, confidence=0.9, summary="Pop-up", location="NYC"
        )
        store.record_detection("m1", "artist", det)  # should not raise
    finally:
        store.close()
        os.remove(path)
