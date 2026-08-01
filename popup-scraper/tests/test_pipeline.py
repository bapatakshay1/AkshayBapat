import os
import tempfile

from popup_scraper.config import Config
from popup_scraper.models import PopupDetection, Post
from popup_scraper.pipeline import Pipeline, compose_message
from popup_scraper.store import Store


def _config(**overrides):
    base = dict(
        ig_username="u",
        ig_password="p",
        ig_session_file="s.json",
        anthropic_api_key="k",
        vision_model="claude-sonnet-5",
        twilio_account_sid="AC",
        twilio_auth_token="t",
        twilio_from_number="+15550000000",
        database_path=":memory:",
        artists_file="artists.yaml",
        confidence_threshold=0.7,
        posts_per_artist=5,
        poll_interval_seconds=1800,
        notifier="console",
    )
    base.update(overrides)
    return Config(**base)


class FakeSource:
    def __init__(self, posts_by_user):
        self._posts = posts_by_user

    def login(self):
        pass

    def follow_artists(self, usernames):
        return {u: True for u in usernames}

    def fetch_recent_posts(self, username, amount):
        return self._posts.get(username, [])[:amount]


class FakeAnalyzer:
    def __init__(self, detections):
        self._detections = detections  # media_id -> PopupDetection

    def analyze(self, post):
        return self._detections[post.media_id]


class FakeNotifier:
    def __init__(self):
        self.blasts = []

    def send_blast(self, phone_numbers, message):
        numbers = list(phone_numbers)
        self.blasts.append((numbers, message))
        return len(numbers)


def _post(media_id, user="artist"):
    return Post(
        media_id=media_id,
        artist_username=user,
        caption="caption",
        image_urls=["http://img"],
        permalink=f"https://instagram.com/p/{media_id}/",
    )


def test_compose_message_has_key_fields():
    post = _post("m1")
    det = PopupDetection(
        is_popup=True,
        confidence=0.9,
        summary="Ceramics sale",
        location="90 Kent Ave, Brooklyn",
        starts_at="Sat 11am",
    )
    msg = compose_message(post, det)
    assert "@artist" in msg
    assert "90 Kent Ave, Brooklyn" in msg
    assert "Sat 11am" in msg
    assert post.permalink in msg
    assert "STOP" in msg


def test_run_once_blasts_on_popup():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = Store(path)
    try:
        store.add_subscriber("+15551110000")
        posts = {"artist": [_post("m1"), _post("m2")]}
        detections = {
            "m1": PopupDetection(is_popup=True, confidence=0.95, summary="Pop-up!",
                                 location="NYC"),
            "m2": PopupDetection(is_popup=False, confidence=0.99, summary="Just art"),
        }
        notifier = FakeNotifier()
        pipeline = Pipeline(
            _config(), FakeSource(posts), FakeAnalyzer(detections), notifier, store
        )
        stats = pipeline.run_once(["artist"])

        assert stats.posts_checked == 2
        assert stats.new_posts == 2
        assert stats.popups_found == 1
        assert stats.blasts_sent == 1
        assert len(notifier.blasts) == 1

        # Second run: everything already seen, no new blasts.
        stats2 = pipeline.run_once(["artist"])
        assert stats2.new_posts == 0
        assert len(notifier.blasts) == 1
    finally:
        store.close()
        os.remove(path)


def test_low_confidence_does_not_blast():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = Store(path)
    try:
        store.add_subscriber("+15551110000")
        posts = {"artist": [_post("m1")]}
        detections = {
            "m1": PopupDetection(is_popup=True, confidence=0.4, summary="Maybe?"),
        }
        notifier = FakeNotifier()
        pipeline = Pipeline(
            _config(), FakeSource(posts), FakeAnalyzer(detections), notifier, store
        )
        stats = pipeline.run_once(["artist"])
        assert stats.popups_found == 0
        assert notifier.blasts == []
    finally:
        store.close()
        os.remove(path)


def test_no_subscribers_marks_notified_without_blast():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = Store(path)
    try:
        posts = {"artist": [_post("m1")]}
        detections = {
            "m1": PopupDetection(is_popup=True, confidence=0.95, summary="Pop-up!"),
        }
        notifier = FakeNotifier()
        pipeline = Pipeline(
            _config(), FakeSource(posts), FakeAnalyzer(detections), notifier, store
        )
        stats = pipeline.run_once(["artist"])
        assert stats.popups_found == 1
        assert stats.blasts_sent == 0
        assert store.was_notified("m1")
    finally:
        store.close()
        os.remove(path)
