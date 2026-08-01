"""Pop-up detection using Claude's vision model.

Downloads a post's image(s), sends them to Claude along with the caption, and
asks for a strict-JSON verdict on whether the artist is hosting a pop-up and
where.
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Optional

from .models import PopupDetection, Post

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You analyze an artist's Instagram post to decide whether it is announcing a \
"pop-up" — a temporary, in-person shopping/market/booth/showcase event where \
the artist sells or exhibits work at a specific place and time.

Look at BOTH the image(s) and the caption. Extract the location as precisely as \
the post allows (venue name, street address, neighborhood, and city).

Respond with ONLY a JSON object, no prose, matching exactly this shape:
{
  "is_popup": boolean,        // true only if this post announces a pop-up event
  "confidence": number,       // 0.0-1.0, your confidence in is_popup
  "venue": string|null,       // e.g. "Smorgasburg", "The Market Hall"
  "location": string|null,    // best full location string you can assemble
  "city": string|null,        // city if determinable
  "starts_at": string|null,   // date/time it starts, as written in the post
  "ends_at": string|null,     // date/time it ends, if given
  "summary": string           // one short sentence a subscriber would find useful
}
If it is clearly not a pop-up, set is_popup false and confidence high."""

_MEDIA_TYPES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG": "image/png",
    b"GIF8": "image/gif",
    b"RIFF": "image/webp",
}


def _guess_media_type(data: bytes) -> str:
    for magic, mime in _MEDIA_TYPES.items():
        if data.startswith(magic):
            return mime
    return "image/jpeg"


class VisionAnalyzer:
    """Wraps the Anthropic client to classify posts as pop-ups."""

    def __init__(self, api_key: str, model: str, max_images: int = 3):
        self._api_key = api_key
        self._model = model
        self._max_images = max_images
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic  # lazy import

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def analyze(self, post: Post) -> PopupDetection:
        images = self._download_images(post.image_urls[: self._max_images])
        if not images:
            return PopupDetection(
                is_popup=False,
                confidence=0.0,
                summary="No image could be downloaded for analysis.",
            )

        content: list[dict] = []
        for data in images:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": _guess_media_type(data),
                        "data": base64.b64encode(data).decode("ascii"),
                    },
                }
            )
        content.append(
            {
                "type": "text",
                "text": f"Caption:\n{post.caption or '(no caption)'}",
            }
        )

        client = self._get_client()
        message = client.messages.create(
            model=self._model,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
        text = _first_text(message)
        return _parse_detection(text)

    def _download_images(self, urls: list[str]) -> list[bytes]:
        import httpx  # lazy import so parsing logic is usable without it

        out: list[bytes] = []
        for url in urls:
            try:
                resp = httpx.get(url, timeout=30, follow_redirects=True)
                resp.raise_for_status()
                out.append(resp.content)
            except Exception as exc:  # pragma: no cover - network path
                logger.warning("Failed to download image %s: %s", url, exc)
        return out


def _first_text(message) -> str:
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""


def _parse_detection(text: str) -> PopupDetection:
    """Parse the model's JSON reply defensively."""
    payload = _extract_json(text)
    if payload is None:
        logger.warning("Vision model did not return parseable JSON: %r", text[:200])
        return PopupDetection(
            is_popup=False,
            confidence=0.0,
            summary="Model response could not be parsed.",
            raw={"text": text},
        )
    return PopupDetection(
        is_popup=bool(payload.get("is_popup", False)),
        confidence=float(payload.get("confidence", 0.0) or 0.0),
        summary=str(payload.get("summary", "") or ""),
        venue=payload.get("venue"),
        location=payload.get("location"),
        city=payload.get("city"),
        starts_at=payload.get("starts_at"),
        ends_at=payload.get("ends_at"),
        raw=payload,
    )


def _extract_json(text: str) -> Optional[dict]:
    text = text.strip()
    # Strip markdown code fences if present.
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fall back to the first {...} block.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None
