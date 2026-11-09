"""Song identification for stretches of music (paid, optional, budget-capped).

Only the music sections the audio check already found are sent - at most
``MUSIC_ID_MAX_CLIPS`` clips of ``MUSIC_ID_CLIP_SECONDS`` each - never speech-only
audio and never the whole file. A match names a recording; it does not say
whether the creator holds a licence for it.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import Settings
from app.integrations.common import get_http_client
from app.provenance import budget
from app.provenance.common import LookupFailed

log = logging.getLogger(__name__)

SERVICE = "music_id"


def pick_clips(
    non_speech: list[list[float]], clip_seconds: float, max_clips: int, min_seconds: float = 4.0
) -> list[tuple[float, float]]:
    """Longest music stretches first, each trimmed to ``clip_seconds``."""
    spans = sorted(
        ((float(a), float(b)) for a, b in non_speech if float(b) - float(a) >= min_seconds),
        key=lambda s: s[1] - s[0],
        reverse=True,
    )
    clips = []
    for start, end in spans[:max_clips]:
        length = min(clip_seconds, end - start)
        middle = start + (end - start - length) / 2
        clips.append((round(middle, 2), round(middle + length, 2)))
    return sorted(clips)


def cut_clip(video: Path, start: float, end: float, out: Path) -> bytes:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start:.2f}",
            "-t",
            f"{end - start:.2f}",
            "-i",
            str(video),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "22050",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "96k",
            str(out),
        ],
        capture_output=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0 or not out.exists():
        raise LookupFailed("Could not cut an audio clip for song identification.")
    data = out.read_bytes()
    out.unlink(missing_ok=True)
    return data


def _audd(clip: bytes, settings: Settings, http: httpx.Client) -> dict[str, Any]:
    assert settings.audd_api_token is not None
    response = http.post(
        settings.audd_api_url,
        data={"api_token": settings.audd_api_token.get_secret_value(), "return": "spotify"},
        files={"file": ("clip.mp3", clip, "audio/mpeg")},
    )
    if response.status_code >= 400:
        raise LookupFailed(f"Song identification service returned HTTP {response.status_code}.")
    body = response.json()
    if body.get("status") != "success":
        code = (body.get("error") or {}).get("error_code")
        raise LookupFailed(f"Song identification failed (provider error {code}).")
    result = body.get("result")
    if not result:
        return {"matched": False}
    spotify = result.get("spotify") or {}
    return {
        "matched": True,
        "title": result.get("title"),
        "artist": result.get("artist"),
        "album": result.get("album"),
        "label": result.get("label"),
        "release_date": result.get("release_date"),
        "song_link": result.get("song_link"),
        "isrc": ((spotify.get("external_ids") or {}).get("isrc")),
    }


def _mock() -> dict[str, Any]:
    return {
        "matched": True,
        "title": "MOCK TRACK (not a real identification)",
        "artist": "Mock Artist",
        "album": None,
        "label": "Mock Label",
        "release_date": None,
        "song_link": None,
        "isrc": None,
    }


def identify(
    db: Session,
    video: Path,
    work_dir: Path,
    non_speech: list[list[float]],
    settings: Settings,
    analysis_id: Any,
) -> dict[str, Any]:
    """Return the ``music`` provenance block. Never raises for expected failures."""
    provider = settings.music_id_provider
    block: dict[str, Any] = {
        "provider": provider,
        "is_mock": provider == "mock",
        "status": "not_configured",
        "clips": [],
        "detail": None,
    }
    if not settings.music_id_configured:
        block["detail"] = (
            "Song identification is off. Set MUSIC_ID_PROVIDER=audd and AUDD_API_TOKEN "
            "to enable it."
        )
        return block
    clips = pick_clips(non_speech, settings.music_id_clip_seconds, settings.music_id_max_clips)
    if not clips:
        block["status"] = "no_music"
        block["detail"] = "No stretch of music long enough to identify."
        return block
    block["status"] = "completed"
    with get_http_client() as http:
        for start, end in clips:
            entry: dict[str, Any] = {"start": start, "end": end}
            try:
                clip = cut_clip(video, start, end, work_dir / "music_clip.mp3")
                key = budget.cache_key(SERVICE, provider, clip)
                hit = budget.cached(db, key, settings)
                if hit is not None:
                    entry.update(hit, cached=True)
                elif provider == "mock":
                    entry.update(_mock(), cached=False)
                else:
                    cost = settings.audd_cost_per_request_usd
                    budget.reserve(db, cost, settings)
                    result = _audd(clip, settings, http)
                    budget.record(
                        db,
                        service=SERVICE,
                        provider=provider,
                        key=key,
                        est_cost=cost,
                        response=result,
                        analysis_id=analysis_id,
                    )
                    entry.update(result, cached=False)
            except budget.BudgetExceeded as exc:
                entry.update(matched=False, error=exc.user_message)
                block["status"] = "budget_exceeded"
            except LookupFailed as exc:
                entry.update(matched=False, error=exc.user_message)
                block["status"] = "partial"
            except httpx.HTTPError:
                log.warning("song identification request failed")
                entry.update(matched=False, error="Song identification service unreachable.")
                block["status"] = "partial"
            block["clips"].append(entry)
    return block
