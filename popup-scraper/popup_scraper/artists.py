"""Loading the watched-artist list from YAML."""
from __future__ import annotations

from pathlib import Path

import yaml


def load_artists(path: str | Path) -> list[str]:
    """Read artists.yaml and return a de-duplicated list of handles.

    Accepts either a top-level list, or a mapping with an `artists:` key whose
    value is a list of strings (or {username: ...} entries).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Artists file not found: {p}. Copy artists.example.yaml to {p}."
        )
    data = yaml.safe_load(p.read_text()) or []
    if isinstance(data, dict):
        data = data.get("artists", [])

    handles: list[str] = []
    for entry in data:
        if isinstance(entry, str):
            handle = entry
        elif isinstance(entry, dict):
            handle = entry.get("username") or entry.get("handle") or ""
        else:
            handle = ""
        handle = handle.strip().lstrip("@")
        if handle and handle not in handles:
            handles.append(handle)
    return handles
