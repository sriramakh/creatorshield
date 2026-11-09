"""Job queue (Redis + RQ) and retention cleanup."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from redis import Redis
from rq import Queue
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Analysis, MediaFingerprint
from app.storage import analysis_prefix, get_storage

log = logging.getLogger(__name__)


def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url)


def get_queue() -> Queue:
    settings = get_settings()
    return Queue(
        settings.queue_name, connection=get_redis(), default_timeout=settings.job_timeout_seconds
    )


def enqueue_analysis(analysis_id: str) -> None:
    settings = get_settings()
    if settings.use_job_queue:
        get_queue().enqueue(
            "app.analysis.engine.process_analysis",
            analysis_id,
            job_id=f"analysis-{analysis_id}-{int(datetime.now(UTC).timestamp())}",
            result_ttl=3600,
            failure_ttl=86400,
        )
    else:
        from app.analysis.engine import process_analysis

        process_analysis(analysis_id)


def delete_analysis(db: Session, analysis: Analysis, keep_fingerprint: bool = False) -> None:
    """Delete an analysis and its media.

    A user's explicit delete also removes the catalogue fingerprint. Retention
    expiry keeps it (it holds no media) until the catalogue retention ends.
    """
    get_storage().delete_prefix(analysis_prefix(analysis.id))
    if not keep_fingerprint:
        db.execute(delete(MediaFingerprint).where(MediaFingerprint.analysis_id == analysis.id))
    db.delete(analysis)
    db.commit()


def purge_expired(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    expired = db.scalars(select(Analysis).where(Analysis.expires_at < now)).all()
    for a in expired:
        delete_analysis(db, a, keep_fingerprint=True)
    if expired:
        log.info("purged %d expired analyses", len(expired))
    from app.provenance.catalogue import purge_expired as purge_fingerprints

    purge_fingerprints(db, now)
    return len(expired)
