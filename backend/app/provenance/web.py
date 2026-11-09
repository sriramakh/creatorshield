"""Reverse image search of a few key frames (paid, optional, budget-capped).

Uses Google Cloud Vision WEB_DETECTION, which reports web pages and images that
contain the same or a similar picture. It finds stock photos, film and TV
stills, news imagery, memes and YouTube thumbnails. It rarely finds frames from
inside Reels or TikToks, which are not indexed as images. A match is a lead to
an earlier source, not proof of who owns it.
"""

from __future__ import annotations

import base64
import logging
import re
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.config import Settings
from app.integrations.common import get_http_client
from app.provenance import budget
from app.provenance.common import LookupFailed
from app.provenance.fingerprint import frame_distance_matrix, thumbnail_hash

log = logging.getLogger(__name__)

SERVICE = "web_detection"
_TAG = re.compile(r"<[^>]+>")
_MAX_URLS = 5
_MAX_PAGES = 8


def pick_frames(
    frames: list[dict[str, Any]],
    frames_dir: Path,
    priority_ids: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    """Frames flagged by cues first, then scene changes; near-duplicates dropped."""
    available = [f for f in frames if (frames_dir / f["file"]).exists()]
    order = {fid: i for i, fid in enumerate(priority_ids)}
    available.sort(
        key=lambda f: (
            order.get(f["id"], len(order)),
            0 if f.get("reason") == "scene" else 1,
            f.get("timestamp") or 0,
        )
    )
    chosen: list[dict[str, Any]] = []
    hashes: list[str] = []
    for frame in available:
        h = thumbnail_hash(frames_dir / frame["file"])
        if h is None:
            continue  # blank or flat frame: nothing to search for
        if hashes:
            dist, _, _ = frame_distance_matrix([h], list(hashes))
            if float(dist.min()) <= 0.25:
                continue
        chosen.append(frame)
        hashes.append(h)
        if len(chosen) >= limit:
            break
    return chosen


def _clean(text: str | None) -> str:
    return unescape(_TAG.sub("", text or "")).strip()[:200]


def _domain(url: str) -> str:
    return (urlparse(url).hostname or "").removeprefix("www.")


def summarise(web: dict[str, Any]) -> dict[str, Any]:
    pages = [
        {
            "url": p.get("url"),
            "title": _clean(p.get("pageTitle")),
            "domain": _domain(str(p.get("url") or "")),
            "full_match": bool(p.get("fullMatchingImages")),
        }
        for p in (web.get("pagesWithMatchingImages") or [])
        if str(p.get("url") or "").startswith(("http://", "https://"))
    ][:_MAX_PAGES]
    return {
        "full_matches": [i.get("url") for i in web.get("fullMatchingImages") or []][:_MAX_URLS],
        "partial_matches": [i.get("url") for i in web.get("partialMatchingImages") or []][
            :_MAX_URLS
        ],
        "pages": pages,
        "best_guess": [_clean(b.get("label")) for b in web.get("bestGuessLabels") or []][:3],
        "entities": [
            _clean(e.get("description"))
            for e in web.get("webEntities") or []
            if e.get("description")
        ][:5],
    }


def _google(images: list[bytes], settings: Settings, http: httpx.Client) -> list[dict[str, Any]]:
    assert settings.google_vision_api_key is not None
    body = {
        "requests": [
            {
                "image": {"content": base64.standard_b64encode(img).decode("ascii")},
                "features": [{"type": "WEB_DETECTION", "maxResults": 10}],
            }
            for img in images
        ]
    }
    response = http.post(
        settings.google_vision_url,
        params={"key": settings.google_vision_api_key.get_secret_value()},
        json=body,
    )
    if response.status_code >= 400:
        raise LookupFailed(f"Web image search returned HTTP {response.status_code}.")
    out = []
    for item in response.json().get("responses") or []:
        if item.get("error"):
            out.append({"error": "The image search service could not process this frame."})
        else:
            out.append(summarise(item.get("webDetection") or {}))
    return out


def _mock() -> dict[str, Any]:
    return {
        "full_matches": [],
        "partial_matches": [],
        "pages": [
            {
                "url": "https://example.com/mock-page",
                "title": "MOCK RESULT (not a real web match)",
                "domain": "example.com",
                "full_match": True,
            }
        ],
        "best_guess": ["mock"],
        "entities": [],
    }


def search(
    db: Session,
    frames: list[dict[str, Any]],
    frames_dir: Path,
    priority_ids: list[str],
    settings: Settings,
    analysis_id: Any,
) -> dict[str, Any]:
    """Return the ``web`` provenance block. Never raises for expected failures."""
    provider = settings.web_detection_provider
    block: dict[str, Any] = {
        "provider": provider,
        "is_mock": provider == "mock",
        "status": "not_configured",
        "frames": [],
        "detail": None,
    }
    if not settings.web_detection_configured:
        block["detail"] = (
            "Web image search is off. Set WEB_DETECTION_PROVIDER=google and "
            "GOOGLE_VISION_API_KEY to enable it."
        )
        return block
    chosen = pick_frames(frames, frames_dir, priority_ids, settings.web_detection_max_frames)
    if not chosen:
        block["status"] = "no_frames"
        block["detail"] = "No frames with enough detail are available (media may be deleted)."
        return block

    pending: list[tuple[dict[str, Any], bytes, str]] = []
    for frame in chosen:
        data = (frames_dir / frame["file"]).read_bytes()
        key = budget.cache_key(SERVICE, provider, data)
        entry = {"frame_id": frame["id"], "timestamp": frame.get("timestamp")}
        hit = budget.cached(db, key, settings)
        if hit is not None:
            block["frames"].append({**entry, **hit, "cached": True})
        elif provider == "mock":
            block["frames"].append({**entry, **_mock(), "cached": False})
        else:
            pending.append((entry, data, key))
    block["status"] = "completed"
    if not pending:
        return block

    cost = settings.web_detection_cost_per_image_usd
    try:
        budget.reserve(db, cost * len(pending), settings)
        with get_http_client() as http:
            results = _google([data for _, data, _ in pending], settings, http)
    except budget.BudgetExceeded as exc:
        block["status"] = "budget_exceeded"
        block["detail"] = exc.user_message
        return block
    except LookupFailed as exc:
        block["status"] = "failed"
        block["detail"] = exc.user_message
        return block
    except httpx.HTTPError:
        log.warning("web image search request failed")
        block["status"] = "failed"
        block["detail"] = "Web image search service unreachable."
        return block
    for (entry, _, key), result in zip(pending, results, strict=False):
        if "error" not in result:
            budget.record(
                db,
                service=SERVICE,
                provider=provider,
                key=key,
                est_cost=cost,
                response=result,
                analysis_id=analysis_id,
            )
        block["frames"].append({**entry, **result, "cached": False})
    block["frames"].sort(key=lambda f: f.get("timestamp") or 0)
    return block
