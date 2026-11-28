"""YouTube look-alike search through the official Data API (search.list).

search.list matches titles and descriptions only, costs 100 quota units per
call and returns public metadata. Candidate videos are never downloaded: only
their public thumbnail is fetched (from the allow-listed thumbnail host),
compared with this video's frame fingerprints, and discarded.
"""

from __future__ import annotations

import logging
import re
import tempfile
from collections import Counter
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.integrations.common import IntegrationError, _redis, get_http_client
from app.integrations.connections import access_token
from app.media.probe import MediaError
from app.models import PlatformConnection
from app.provenance.common import LookupFailed
from app.provenance.fingerprint import nearest_frame, thumbnail_hash

log = logging.getLogger(__name__)

SEARCH_COST_UNITS = 100
THUMB_MAX_BYTES = 2_000_000
STRONG_VISUAL = 0.12
POSSIBLE_VISUAL = 0.2
_STOP = {
    "the", "and", "for", "you", "your", "this", "that", "with", "are", "was", "but", "not",
    "have", "has", "from", "what", "will", "can", "all", "just", "like", "get", "out", "our",
    "how", "its", "into", "about", "they", "them", "then", "there", "here", "when", "who",
    "aur", "hai", "hain", "main", "mein", "kya", "nahi", "bhi", "toh", "yeh", "woh", "aap",
    "है", "हैं", "और", "में", "की", "का", "के", "को", "से", "यह", "वह", "आप", "मैं", "भी",
    "use", "code", "link", "bio", "follow", "subscribe", "share", "comment",
}  # fmt: skip
_WORD = re.compile(r"[^\W\d_][\w'’]+", re.UNICODE)


def suggest_query(caption: str, title: str | None, transcript: list[dict[str, Any]]) -> str:
    """A short keyword query from the title/caption and the most frequent spoken words."""
    words: Counter[str] = Counter()
    for seg in transcript:
        for w in _WORD.findall(str(seg.get("text") or "")):
            if len(w) >= 4 and w.casefold() not in _STOP:
                words[w.casefold()] += 1
    head = (title or caption or "").split("\n")[0]
    head = re.sub(r"[#@]\S+", "", head).strip()
    head_words = [w for w in _WORD.findall(head) if w.casefold() not in _STOP][:6]
    extra = [w for w, _ in words.most_common(6) if w not in {h.casefold() for h in head_words}]
    return " ".join(head_words + extra)[:120].strip()


def _quota_day(now: datetime | None = None) -> str:
    """YouTube Data API quotas reset at midnight Pacific Time, so count per Pacific day."""
    now = now or datetime.now(UTC)
    try:
        pacific: tzinfo = ZoneInfo("America/Los_Angeles")
    except ZoneInfoNotFoundError:  # no tz database: PST, at worst an hour early in summer
        pacific = timezone(timedelta(hours=-8))
    return now.astimezone(pacific).date().isoformat()


def _quota_key(now: datetime | None = None) -> str:
    return f"creatorshield:yt-search-units:{_quota_day(now)}"


def quota_used() -> int:
    try:
        value = _redis().get(_quota_key())
    except Exception:
        return 0
    return int(value or 0)


def _spend_quota(settings: Settings) -> None:
    """Atomically take SEARCH_COST_UNITS from today's allowance (or refuse)."""
    try:
        redis = _redis()
        key = _quota_key()
        used = int(redis.incrby(key, SEARCH_COST_UNITS))
        redis.expire(key, 60 * 60 * 36)
        if used > settings.youtube_search_daily_unit_cap:
            redis.decrby(key, SEARCH_COST_UNITS)
            raise LookupFailed(
                f"Today's YouTube search allowance is used up ({used - SEARCH_COST_UNITS} of "
                f"{settings.youtube_search_daily_unit_cap} quota units). It resets at midnight "
                "Pacific Time."
            )
    except LookupFailed:
        raise
    except Exception as exc:  # Redis unavailable: do not search without a quota counter
        raise LookupFailed("YouTube search is unavailable (quota counter unreachable).") from exc


def _auth(
    db: Session, settings: Settings, own_channel_ids: set[str]
) -> tuple[dict[str, str], dict[str, str]]:
    """(query params, headers). API key preferred; else the token of one of this
    client's own connected channels (never another client's)."""
    if settings.youtube_search_api_key and settings.youtube_search_api_key.get_secret_value():
        return {"key": settings.youtube_search_api_key.get_secret_value()}, {}
    conn = (
        db.scalars(
            select(PlatformConnection).where(
                PlatformConnection.platform == "youtube",
                PlatformConnection.external_id.in_(sorted(own_channel_ids)),
            )
        ).first()
        if own_channel_ids
        else None
    )
    if conn is None:
        raise LookupFailed(
            "YouTube search needs YOUTUBE_SEARCH_API_KEY or a connected YouTube channel "
            "belonging to this client."
        )
    try:
        token = access_token(db, conn, settings)
    except IntegrationError as exc:
        raise LookupFailed(exc.user_message) from exc
    return {}, {"Authorization": f"Bearer {token}"}


def _thumb_allowed(url: str, hosts: list[str]) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(host == h or host.endswith("." + h) for h in hosts)


def search(
    db: Session,
    query: str,
    frame_hashes: list[str | None],
    frame_step: float,
    settings: Settings,
    own_channels: set[str] | None = None,
) -> dict[str, Any]:
    """``own_channels``: YouTube channel ids that belong to the analysed post's client
    (see ``ledger.connected_accounts_for``). Other connected channels are results
    like any other."""
    own_channels = set(own_channels or set())
    query = re.sub(r"\s+", " ", query).strip()[:120]
    if len(query) < 3:
        raise LookupFailed("Enter a few words to search for.")
    params, headers = _auth(db, settings, own_channels)
    _spend_quota(settings)
    with get_http_client() as http:
        try:
            response = http.get(
                f"{settings.youtube_api_url}/search",
                params={
                    **params,
                    "part": "snippet",
                    "type": "video",
                    "q": query,
                    "maxResults": 25,
                    "videoDuration": "short",
                    "safeSearch": "none",
                },
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise LookupFailed("YouTube search is unreachable.") from exc
        if response.status_code == 403:
            raise LookupFailed("YouTube refused the search (quota or API key restrictions).")
        if response.status_code >= 400:
            raise LookupFailed(f"YouTube search returned HTTP {response.status_code}.")
        try:
            payload = response.json()
        except ValueError as exc:
            raise LookupFailed("YouTube search returned an unreadable answer.") from exc
        raw_items = payload.get("items") if isinstance(payload, dict) else None
        items = [i for i in raw_items or [] if isinstance(i, dict)]
        results = []
        with tempfile.TemporaryDirectory(prefix="cs-thumb-") as tmp:
            for item in items:
                video_id = (item.get("id") or {}).get("videoId")
                snippet = item.get("snippet") or {}
                if not video_id:
                    continue
                thumbs = snippet.get("thumbnails") or {}
                thumb_url = str(
                    (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get(
                        "url"
                    )
                    or ""
                )
                visual = _compare_thumbnail(
                    http, thumb_url, Path(tmp), frame_hashes, frame_step, settings
                )
                results.append(
                    {
                        "video_id": video_id,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "title": str(snippet.get("title") or "")[:200],
                        "channel_title": str(snippet.get("channelTitle") or "")[:120],
                        "channel_id": snippet.get("channelId"),
                        "published_at": snippet.get("publishedAt"),
                        "thumbnail_url": thumb_url
                        if _thumb_allowed(thumb_url, settings.youtube_thumbnail_hosts)
                        else None,
                        "own_channel": snippet.get("channelId") in own_channels,
                        **visual,
                    }
                )
    results.sort(key=lambda r: (r["visual_distance"] is None, r["visual_distance"] or 1.0))
    return {
        "status": "completed",
        "query": query,
        "searched_at": datetime.now(UTC).isoformat(),
        "quota_units": SEARCH_COST_UNITS,
        "results": results,
        "strong_matches": sum(1 for r in results if r["visual_match"] == "strong"),
    }


def _compare_thumbnail(
    http: httpx.Client,
    url: str,
    tmp: Path,
    frame_hashes: list[str | None],
    frame_step: float,
    settings: Settings,
) -> dict[str, Any]:
    none = {"visual_distance": None, "visual_match": "unknown", "matched_at": None}
    if not url or not _thumb_allowed(url, settings.youtube_thumbnail_hosts):
        return none
    path = tmp / "thumb.img"
    data = bytearray()
    try:
        with http.stream("GET", url) as resp:
            if resp.status_code != 200:
                return none
            for chunk in resp.iter_bytes(64 * 1024):
                data += chunk
                if len(data) > THUMB_MAX_BYTES:
                    return none
    except httpx.HTTPError:
        return none
    path.write_bytes(bytes(data))
    try:
        h = thumbnail_hash(path)
    except MediaError:
        h = None
    finally:
        path.unlink(missing_ok=True)
    if h is None:
        return none
    nearest = nearest_frame(h, frame_hashes, frame_step)
    if nearest is None:
        return none
    distance, at = nearest
    label = (
        "strong"
        if distance <= STRONG_VISUAL
        else "possible"
        if distance <= POSSIBLE_VISUAL
        else "none"
    )
    return {"visual_distance": distance, "visual_match": label, "matched_at": at}
