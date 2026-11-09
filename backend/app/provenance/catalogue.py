"""Catalogue of fingerprints: every reviewed video plus past posts indexed on purpose.

New videos are compared with the catalogue to find reposts of the same client's
older posts and, for agencies, the same footage appearing under a different
client - a sign that at least one of them may not own it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Analysis, MediaFingerprint, PlatformConnection
from app.provenance.fingerprint import Fingerprint, compare
from app.provenance.ledger import normalise

UNLABELLED = "Unlabelled uploads"
MIN_MATCH_SECONDS = 3.0


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


def find_matches(
    db: Session, fp: Fingerprint, owner_label: str, exclude_id: uuid.UUID | None, settings: Settings
) -> dict[str, Any]:
    rows = db.scalars(
        select(MediaFingerprint)
        .where(MediaFingerprint.expires_at > datetime.now(UTC))
        .order_by(MediaFingerprint.created_at.desc())
        .limit(settings.catalogue_scan_limit)
    ).all()
    matches = []
    me = normalise(owner_label)
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
            result = compare(fp, as_fingerprint(row))
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
    return {"entries_checked": len(rows), "owner_label": owner_label, "matches": matches[:20]}


def purge_expired(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    result = db.execute(delete(MediaFingerprint).where(MediaFingerprint.expires_at < now))
    db.commit()
    return int(getattr(result, "rowcount", 0) or 0)
