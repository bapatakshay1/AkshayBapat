import tempfile
from pathlib import Path

import pytest

from popup_scraper.artists import load_artists


def _write(content):
    p = Path(tempfile.mkstemp(suffix=".yaml")[1])
    p.write_text(content)
    return p


def test_load_mapping_form():
    p = _write("artists:\n  - alice\n  - '@bob'\n  - alice\n")
    assert load_artists(p) == ["alice", "bob"]


def test_load_list_form():
    p = _write("- alice\n- bob\n")
    assert load_artists(p) == ["alice", "bob"]


def test_load_username_dicts():
    p = _write("artists:\n  - username: alice\n  - username: bob\n")
    assert load_artists(p) == ["alice", "bob"]


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_artists("/nonexistent/path/artists.yaml")
