"""Catalogue of fingerprints: every reviewed video plus past posts indexed on purpose.

New videos are compared with the catalogue to find reposts of the same client's
older posts and, for agencies, the same footage appearing under a different
client - a sign that at least one of them may not own it.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Analysis, MediaFingerprint, PlatformConnection
from app.provenance.fingerprint import (
    AUDIO_MIN_ITEMS,
    VIDEO_MIN_ALIGNED,
    Fingerprint,
    compare_prepared,
    prepare,
)
from app.provenance.ledger import normalise

UNLABELLED = "Unlabelled uploads"
MIN_MATCH_SECONDS = 3.0
COMPARE_SECONDS_MAX = 600.0
# Upper bound on query x reference frame pairs per video (about 115 comparisons
# of two 30-minute videos). With the time budget it keeps one review bounded.
MAX_PAIR_WORK = 1_500_000_000


def owner_label_for(db: Session, analysis: Analysis) -> str:
    if analysis.client_label and analysis.client_label.strip():
        return analysis.client_label.strip()[:100]
    if analysis.connection_id:
        conn = db.get(PlatformConnection, analysis.connection_id)
        if conn is not None:
            return conn.display_name[:100]
    return UNLABELLED


def fingerprint_expiry(source: str, settings: Settings) -> datetime:
    hours = settings.catalogue_retention_days * 24
    if source == "youtube":
        # YouTube API data (the title stored alongside) must not outlive 30 days.
        hours = min(hours, settings.youtube_max_retention_hours)
    return datetime.now(UTC) + timedelta(hours=hours)


def save_for_analysis(
    db: Session, analysis: Analysis, fp: Fingerprint, settings: Settings
) -> MediaFingerprint:
    db.execute(delete(MediaFingerprint).where(MediaFingerprint.analysis_id == analysis.id))
    row = MediaFingerprint(
        source="analysis",
        analysis_id=analysis.id,
        connection_id=analysis.connection_id,
        owner_label=owner_label_for(db, analysis),
        platform=analysis.platform,
        title=(analysis.source_title or (analysis.caption or "").split("\n")[0] or None),
        duration_seconds=fp.duration_seconds,
        sha256=fp.sha256,
        frame_step=fp.frame_step,
        frame_hashes=fp.frame_hashes,
        audio_step=fp.audio_step,
        audio_fp=fp.audio_fp,
        expires_at=fingerprint_expiry(analysis.source, settings),
    )
    if row.title:
        row.title = row.title[:300]
    db.add(row)
    db.commit()
    return row


def as_fingerprint(row: MediaFingerprint) -> Fingerprint:
    return Fingerprint(
        duration_seconds=row.duration_seconds,
        sha256=row.sha256,
        frame_step=row.frame_step,
        frame_hashes=list(row.frame_hashes or []),
        audio_step=row.audio_step,
        audio_fp=list(row.audio_fp or []),
    )


def compare_budget_seconds(settings: Settings) -> float:
    """Wall-clock budget for comparing one video with the catalogue.

    Kept well inside the job timeout so the rest of the review still runs.
    """
    configured = getattr(settings, "catalogue_compare_seconds", None)
    if configured:
        return float(configured)
    return max(30.0, min(COMPARE_SECONDS_MAX, settings.job_timeout_seconds * 0.15))


def find_matches(
    db: Session,
    fp: Fingerprint,
    owner_label: str,
    exclude_id: uuid.UUID | None,
    settings: Settings,
    *,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    rows = db.scalars(
        select(MediaFingerprint)
        .where(MediaFingerprint.expires_at > datetime.now(UTC))
        .order_by(MediaFingerprint.created_at.desc())
        .limit(settings.catalogue_scan_limit)
    ).all()
    matches = []
    me = normalise(owner_label)
    pq = prepare(fp)
    deadline = clock() + compare_budget_seconds(settings)
    query_frames = max(1, len(fp.frame_hashes))
    work = 0
    compared = 0
    truncated_note = None
    for row in rows:
        if exclude_id is not None and row.id == exclude_id:
            continue
        if row.sha256 == fp.sha256:
            result: dict[str, Any] | None = {
                "kind": "identical_file",
                "query_start": 0.0,
                "query_end": fp.duration_seconds,
                "ref_start": 0.0,
                "ref_end": row.duration_seconds,
                "video_coverage": 1.0,
                "audio_coverage": 1.0 if fp.audio_fp else 0.0,
                "video_score": 1.0,
                "audio_score": 1.0 if fp.audio_fp else None,
                "audio_segment": None,
            }
        else:
            if clock() > deadline or work > MAX_PAIR_WORK:
                truncated_note = (
                    f"Compared with {compared} of {len(rows)} catalogue entries (newest first); "
                    "the rest were skipped to keep the review within its time limit. "
                    "Identical files were still checked."
                )
                continue
            if not _could_match(fp, row):
                compared += 1
                continue
            work += query_frames * max(1, len(row.frame_hashes or []))
            compared += 1
            result = compare_prepared(pq, as_fingerprint(row))
        if result is None:
            continue
        span = result["query_end"] - result["query_start"]
        # Byte-identical files are the same clip however short. The floor only
        # drops weak perceptual overlaps.
        if result["kind"] != "identical_file" and span < MIN_MATCH_SECONDS:
            continue
        same_owner = me != normalise(UNLABELLED) and normalise(row.owner_label) == me
        matches.append(
            {
                **result,
                "fingerprint_id": str(row.id),
                "analysis_id": str(row.analysis_id) if row.analysis_id else None,
                "source": row.source,
                "owner_label": row.owner_label,
                "same_owner": same_owner,
                "unlabelled": normalise(row.owner_label) == normalise(UNLABELLED)
                or me == normalise(UNLABELLED),
                "platform": row.platform,
                "title": row.title,
                "indexed_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    rank = {"identical_file": 0, "same_clip": 1, "same_footage": 2, "mirrored_footage": 2}
    matches.sort(
        key=lambda m: (
            rank.get(m["kind"], 3),
            -max(m["video_coverage"], m["audio_coverage"]),
        )
    )
    out: dict[str, Any] = {
        "entries_checked": len(rows),
        "entries_compared": compared,
        "owner_label": owner_label,
        "matches": matches[:20],
    }
    if truncated_note:
        out["truncated"] = True
        out["truncated_note"] = truncated_note
    return out


def _could_match(fp: Fingerprint, row: MediaFingerprint) -> bool:
    """Entries too short or too blank to reach the match floor are not compared."""
    min_frames = VIDEO_MIN_ALIGNED
    has_video = (
        sum(1 for h in fp.frame_hashes if h) >= min_frames
        and sum(1 for h in row.frame_hashes or [] if h) >= min_frames
    )
    has_audio = len(fp.audio_fp) >= AUDIO_MIN_ITEMS and len(row.audio_fp or []) >= AUDIO_MIN_ITEMS
    return has_video or has_audio


def purge_expired(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    result = db.execute(delete(MediaFingerprint).where(MediaFingerprint.expires_at < now))
    db.commit()
    return int(getattr(result, "rowcount", 0) or 0)
