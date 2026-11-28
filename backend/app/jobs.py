"""Job queue (Redis + RQ), retention cleanup and periodic maintenance."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from redis import Redis
from rq import Queue
from rq.registry import StartedJobRegistry
from sqlalchemy import delete, select, text, update
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_engine, get_sessionmaker
from app.models import Analysis, AnalysisStat, MediaFingerprint, PaidLookup, RightsRecord
from app.storage import analysis_prefix, get_storage

log = logging.getLogger(__name__)

JOB_FUNC = "app.jobs.run_analysis_job"
_JOB_ID_RE = re.compile(r"^analysis-([0-9a-fA-F-]{36})-")
# Session-level Postgres advisory lock: one maintenance run at a time across
# every API and worker process sharing the database.
MAINTENANCE_LOCK_KEY = 0x435348_4D41494E  # "CSH" "MAIN"
# Cache key written over a detached paid lookup so it can never serve as a cache hit.
PURGED_CACHE_KEY = "purged"
STUCK_PROCESSING_MESSAGE = (
    "Processing stopped before it finished (the worker restarted, crashed or ran past "
    "its time limit). Use Rerun to try again."
)
LOST_QUEUE_MESSAGE = (
    "The queued job was lost before it started (the job queue restarted). Use Rerun to try again."
)


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
            JOB_FUNC,
            analysis_id,
            job_id=f"analysis-{analysis_id}-{uuid.uuid4().hex[:12]}",
            job_timeout=settings.job_timeout_seconds,
            result_ttl=3600,
            failure_ttl=86400,
        )
    else:
        run_analysis_job(analysis_id)


def run_analysis_job(analysis_id: str) -> None:
    """RQ entry point: run the pipeline, then clean up if the analysis was deleted.

    A delete (or disconnect) while the job runs removes the row and the files, but
    the pipeline may keep writing frames or a working copy afterwards. Those files
    are removed here so nothing outlives the delete.
    """
    from app.analysis.engine import process_analysis

    try:
        process_analysis(analysis_id)
    finally:
        discard_if_deleted(analysis_id)


def discard_if_deleted(analysis_id: str | uuid.UUID) -> bool:
    """Remove storage and links left by a job whose analysis no longer exists."""
    aid = uuid.UUID(str(analysis_id))
    with get_sessionmaker()() as db:
        if db.get(Analysis, aid) is not None:
            return False
        detach_paid_lookups(db, [aid])
        db.commit()
    get_storage().delete_prefix(analysis_prefix(aid))
    log.info("analysis %s was deleted while processing; removed its remaining files", aid)
    return True


def detach_paid_lookups(db: Session, analysis_ids: Iterable[uuid.UUID]) -> None:
    """Remove the link and stored response of paid lookups made for these analyses.

    The row itself (service, cost, date) stays until the month is over so a delete
    cannot reset the monthly budget; it no longer serves as a cache entry.
    """
    ids = list(analysis_ids)
    if not ids:
        return
    db.execute(
        update(PaidLookup)
        .where(PaidLookup.analysis_id.in_(ids))
        .values(analysis_id=None, response={}, cache_key=PURGED_CACHE_KEY)
    )


def delete_analysis(db: Session, analysis: Analysis, keep_fingerprint: bool = False) -> None:
    """Delete an analysis and its media.

    A user's explicit delete also removes the catalogue fingerprint. Retention
    expiry keeps it (it holds no media) until the catalogue retention ends.
    Paid lookups lose their link and stored response either way.
    """
    aid = analysis.id
    get_storage().delete_prefix(analysis_prefix(aid))
    if not keep_fingerprint:
        db.execute(delete(MediaFingerprint).where(MediaFingerprint.analysis_id == aid))
        # An explicit delete also removes the review's row from insights.
        db.execute(delete(AnalysisStat).where(AnalysisStat.analysis_id == aid))
    detach_paid_lookups(db, [aid])
    db.delete(analysis)
    db.commit()


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def purge_expired(db: Session, now: datetime | None = None) -> int:
    """Delete expired analyses, expired fingerprints and paid lookups no longer needed."""
    now = now or datetime.now(UTC)
    settings = get_settings()
    expired = db.scalars(select(Analysis).where(Analysis.expires_at < now)).all()
    for a in expired:
        delete_analysis(db, a, keep_fingerprint=True)
    if expired:
        log.info("purged %d expired analyses", len(expired))
    from app.provenance.catalogue import purge_expired as purge_fingerprints

    purge_fingerprints(db, now)
    # Paid lookups are kept only while they count towards this month's budget or
    # can still serve as a cache hit.
    keep_after = min(_month_start(now), now - timedelta(days=settings.paid_lookup_cache_days))
    db.execute(delete(PaidLookup).where(PaidLookup.created_at < keep_after))
    stats_cutoff = now - timedelta(days=max(settings.usage_stats_retention_days, 0))
    db.execute(delete(AnalysisStat).where(AnalysisStat.created_at < stats_cutoff))
    db.commit()
    return len(expired)


def _live_job_analysis_ids() -> set[str] | None:
    """Analysis IDs with a job waiting or running in RQ; None if Redis is unreachable."""
    try:
        queue = get_queue()
        ids = set(queue.get_job_ids()) | set(StartedJobRegistry(queue=queue).get_job_ids())
    except Exception:
        log.warning("job queue unreachable; queued analyses are checked by age only")
        return None
    out: set[str] = set()
    for job_id in ids:
        m = _JOB_ID_RE.match(job_id)
        if m:
            out.add(m.group(1).lower())
    return out


def reset_stuck_jobs(db: Session, settings: Settings, now: datetime | None = None) -> int:
    """Mark analyses whose job can no longer be running as failed (Rerun works again).

    - processing: untouched for longer than the job time limit plus a grace period
      (RQ would have stopped the job by then; a crashed worker leaves it behind).
    - queued: no job for it in the queue any more and untouched for the grace period,
      or untouched for longer than the job time limit when the queue cannot be read.
    """
    now = now or datetime.now(UTC)
    hard_cutoff = now - timedelta(
        seconds=settings.job_timeout_seconds + settings.stuck_job_grace_seconds
    )
    grace_cutoff = now - timedelta(seconds=settings.stuck_job_grace_seconds)
    reset = 0
    for a in db.scalars(
        select(Analysis).where(Analysis.status == "processing", Analysis.updated_at < hard_cutoff)
    ).all():
        a.status, a.stage, a.error_message = "failed", "failed", STUCK_PROCESSING_MESSAGE
        reset += 1
    queued = db.scalars(
        select(Analysis).where(Analysis.status == "queued", Analysis.updated_at < grace_cutoff)
    ).all()
    live = _live_job_analysis_ids() if (queued and settings.use_job_queue) else None
    for a in queued:
        lost = str(a.id) not in live if live is not None else a.updated_at < hard_cutoff
        if lost:
            a.status, a.stage, a.error_message = "failed", "failed", LOST_QUEUE_MESSAGE
            reset += 1
    if reset:
        log.warning("reset %d stuck analyses to failed", reset)
    db.commit()
    return reset


def _newest_mtime(path: Path) -> float:
    newest = 0.0
    try:
        newest = path.stat().st_mtime
        for dirpath, dirnames, filenames in os.walk(path):
            for name in [*dirnames, *filenames]:
                try:
                    newest = max(newest, (Path(dirpath) / name).stat().st_mtime)
                except FileNotFoundError:
                    continue
    except FileNotFoundError:
        pass
    return newest


def _stale_uuid_dirs(parent: Path, cutoff: float) -> dict[uuid.UUID, str]:
    out: dict[uuid.UUID, str] = {}
    if not parent.is_dir():
        return out
    for child in parent.iterdir():
        if not child.is_dir():
            continue
        try:
            key = uuid.UUID(child.name)
        except ValueError:
            continue
        if str(key) == child.name and _newest_mtime(child) < cutoff:
            out[key] = child.name
    return out


def sweep_orphan_storage(db: Session, settings: Settings, now: datetime | None = None) -> int:
    """Remove stored files whose database row is gone (left by crashes or races).

    Covers ``analyses/<id>``, ``rights/<id>`` and abandoned ``catalogue/incoming-*``
    files. Anything modified within ``orphan_grace_seconds`` is left alone, so an
    upload still being written (before its row is committed) is never touched.
    """
    now = now or datetime.now(UTC)
    cutoff = now.timestamp() - settings.orphan_grace_seconds
    storage = get_storage()
    root = storage.local_path("analyses").parent
    removed = 0
    for folder, model in (("analyses", Analysis), ("rights", RightsRecord)):
        stale = _stale_uuid_dirs(root / folder, cutoff)
        if not stale:
            continue
        known = set(db.scalars(select(model.id).where(model.id.in_(list(stale)))).all())
        for key, name in stale.items():
            if key not in known:
                storage.delete_prefix(f"{folder}/{name}")
                removed += 1
    incoming = root / "catalogue"
    if incoming.is_dir():
        for f in incoming.glob("incoming-*"):
            try:
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink()
                    removed += 1
            except FileNotFoundError:
                continue
    if removed:
        log.info("removed %d orphaned storage entries", removed)
    return removed


def run_maintenance(now: datetime | None = None) -> dict[str, int] | None:
    """One maintenance pass. Returns None if another process is running one."""
    settings = get_settings()
    engine = get_engine()
    use_lock = engine.dialect.name == "postgresql"
    with engine.connect() as lock_conn:
        if use_lock:
            got = lock_conn.execute(
                text("SELECT pg_try_advisory_lock(:k)"), {"k": MAINTENANCE_LOCK_KEY}
            ).scalar()
            lock_conn.commit()
            if not got:
                return None
        try:
            with get_sessionmaker()() as db:
                return {
                    "stuck_reset": reset_stuck_jobs(db, settings, now),
                    "analyses_purged": purge_expired(db, now),
                    "orphans_removed": sweep_orphan_storage(db, settings, now),
                }
        finally:
            if use_lock:
                lock_conn.execute(
                    text("SELECT pg_advisory_unlock(:k)"), {"k": MAINTENANCE_LOCK_KEY}
                )
                lock_conn.commit()


def _safe_maintenance() -> dict[str, int] | None:
    try:
        return run_maintenance()
    except Exception:
        log.exception("maintenance run failed")
        return None


async def maintenance_loop(interval: float, stop: asyncio.Event) -> None:
    """API-side scheduler: run maintenance now, then every ``interval`` seconds."""
    while not stop.is_set():
        await asyncio.to_thread(_safe_maintenance)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            continue


def start_maintenance_thread(interval: float) -> tuple[threading.Thread, threading.Event]:
    """Worker-side scheduler (the worker's main thread is busy running jobs)."""
    stop = threading.Event()

    def loop() -> None:
        while not stop.wait(interval):
            _safe_maintenance()

    thread = threading.Thread(target=loop, name="maintenance", daemon=True)
    thread.start()
    return thread, stop
