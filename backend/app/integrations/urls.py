"""Strict parsing of pasted Instagram / YouTube links (no fetching happens here)."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from app.integrations.common import IntegrationError

_YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_IG_CODE = re.compile(r"^[A-Za-z0-9_-]{5,64}$")
YT_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
IG_HOSTS = {"instagram.com", "www.instagram.com", "m.instagram.com"}


def _parse(url: str):  # type: ignore[no-untyped-def]
    url = (url or "").strip()
    if len(url) > 500:
        raise IntegrationError("Link is too long.")
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    parsed = urlparse(url)
    return parsed, (parsed.hostname or "").lower()


def parse_youtube_video_id(url: str) -> str:
    parsed, host = _parse(url)
    if host not in YT_HOSTS:
        raise IntegrationError("That is not a YouTube link.")
    parts = [p for p in parsed.path.split("/") if p]
    candidate = ""
    if host == "youtu.be" and parts:
        candidate = parts[0]
    elif parts[:1] == ["watch"]:
        candidate = parse_qs(parsed.query).get("v", [""])[0]
    elif len(parts) >= 2 and parts[0] in ("shorts", "live", "embed", "v"):
        candidate = parts[1]
    if not _YT_ID.match(candidate):
        raise IntegrationError("Could not find a YouTube video ID in that link.")
    return candidate


def parse_instagram_shortcode(url: str) -> str:
    parsed, host = _parse(url)
    if host not in IG_HOSTS:
        raise IntegrationError("That is not an Instagram link.")
    parts = [p for p in parsed.path.split("/") if p]
    # /reel/<code>/, /reels/<code>/, /p/<code>/, /tv/<code>/, optionally /<username>/reel/<code>/
    for i, part in enumerate(parts[:-1]):
        if part in ("reel", "reels", "p", "tv") and _IG_CODE.match(parts[i + 1]):
            return parts[i + 1]
    raise IntegrationError("Could not find an Instagram post code in that link.")
