from popup_scraper.vision import (
    _extract_json,
    _guess_media_type,
    _parse_detection,
)


def test_extract_plain_json():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_fenced_json():
    text = '```json\n{"is_popup": true}\n```'
    assert _extract_json(text) == {"is_popup": True}


def test_extract_json_with_surrounding_prose():
    text = 'Here is the result: {"is_popup": false, "confidence": 0.8} done'
    assert _extract_json(text) == {"is_popup": False, "confidence": 0.8}


def test_extract_json_invalid_returns_none():
    assert _extract_json("not json at all") is None


def test_parse_detection_full():
    text = (
        '{"is_popup": true, "confidence": 0.92, "venue": "Smorgasburg", '
        '"location": "90 Kent Ave, Brooklyn", "city": "Brooklyn", '
        '"starts_at": "Sat 11am", "ends_at": null, "summary": "Selling ceramics."}'
    )
    det = _parse_detection(text)
    assert det.is_popup is True
    assert det.confidence == 0.92
    assert det.venue == "Smorgasburg"
    assert det.city == "Brooklyn"
    assert det.summary == "Selling ceramics."


def test_parse_detection_unparseable_is_safe():
    det = _parse_detection("garbage")
    assert det.is_popup is False
    assert det.confidence == 0.0


def test_guess_media_type():
    assert _guess_media_type(b"\xff\xd8\xff\xe0rest") == "image/jpeg"
    assert _guess_media_type(b"\x89PNG\r\n") == "image/png"
    assert _guess_media_type(b"unknown") == "image/jpeg"
