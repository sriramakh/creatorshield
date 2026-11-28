"""Maintenance: scheduled retention, stuck jobs, delete-while-processing, orphans,
paid-lookup cleanup, rerun enqueue-or-rollback (needs the test database)."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import jobs
from app.analysis import engine
from app.config import get_settings
from app.db import get_sessionmaker
from app.models import Analysis, MediaFingerprint, PaidLookup, RightsRecord
from app.provenance import budget
from app.storage import analysis_prefix, get_storage


def make_analysis(**overrides: object) -> uuid.UUID:
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "expires_at": now + timedelta(hours=72),
        "platform": "youtube_shorts",
        "language": "en",
        "file_ext": ".mp4",
        "content_type": "video/mp4",
        "size_bytes": 10,
        "status": "completed",
        "stage": "completed",
        "progress": 100,
        "limitations": [],
    }
    values.update(overrides)
    with get_sessionmaker()() as db:
        a = Analysis(**values)
        db.add(a)
        db.commit()
        return a.id


def put_file(key: str, data: bytes = b"x") -> None:
    path = get_storage().local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def status_of(aid: uuid.UUID) -> tuple[str, str | None] | None:
    with get_sessionmaker()() as db:
        a = db.get(Analysis, aid)
        return (a.status, a.error_message) if a else None


# ---------------------------------------------------------------- stuck jobs


def test_stuck_processing_and_lost_queued_jobs_are_reset() -> None:
    settings = get_settings()
    old = datetime.now(UTC) - timedelta(seconds=settings.job_timeout_seconds + 3600)
    dead = make_analysis(status="processing", stage="extracting", updated_at=old)
    alive = make_analysis(status="processing", stage="extracting")
    lost_queued = make_analysis(status="queued", stage="queued", updated_at=old)
    fresh_queued = make_analysis(status="queued", stage="queued")
    with get_sessionmaker()() as db:
        assert jobs.reset_stuck_jobs(db, settings) == 2
    assert status_of(dead) == ("failed", jobs.STUCK_PROCESSING_MESSAGE)
    assert status_of(lost_queued) == ("failed", jobs.LOST_QUEUE_MESSAGE)
    assert status_of(alive) is not None and status_of(alive)[0] == "processing"  # type: ignore[index]
    assert status_of(fresh_queued) is not None and status_of(fresh_queued)[0] == "queued"  # type: ignore[index]


def test_queued_job_missing_from_the_queue_is_reset_after_grace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings().model_copy(update={"use_job_queue": True})
    past_grace = datetime.now(UTC) - timedelta(seconds=settings.stuck_job_grace_seconds + 60)
    in_queue = make_analysis(status="queued", stage="queued", updated_at=past_grace)
    gone = make_analysis(status="queued", stage="queued", updated_at=past_grace)
    monkeypatch.setattr(jobs, "_live_job_analysis_ids", lambda: {str(in_queue)})
    with get_sessionmaker()() as db:
        assert jobs.reset_stuck_jobs(db, settings) == 1
    assert status_of(gone) == ("failed", jobs.LOST_QUEUE_MESSAGE)
    assert status_of(in_queue)[0] == "queued"  # type: ignore[index]
    # Queue unreachable: only analyses older than the job time limit are reset.
    monkeypatch.setattr(jobs, "_live_job_analysis_ids", lambda: None)
    with get_sessionmaker()() as db:
        assert jobs.reset_stuck_jobs(db, settings) == 0


def test_reset_job_can_be_rerun(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import app

    old = datetime.now(UTC) - timedelta(days=1)
    aid = make_analysis(
        status="processing", stage="extracting", updated_at=old, storage_key="k/video.mp4"
    )
    with get_sessionmaker()() as db:
        jobs.reset_stuck_jobs(db, get_settings())
    calls: list[str] = []
    monkeypatch.setattr("app.api.routes.enqueue_analysis", calls.append)
    with TestClient(app) as client:
        assert client.post(f"/api/analyses/{aid}/rerun").status_code == 202
    assert calls == [str(aid)]


# ---------------------------------------------------------------- rerun enqueue-or-rollback


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_rerun_rolls_back_when_the_queue_is_down(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    aid = make_analysis(storage_key="analyses/x/video.mp4")

    def down(_id: str) -> None:
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.api.routes.enqueue_analysis", down)
    r = client.post(f"/api/analyses/{aid}/rerun")
    assert r.status_code == 503
    # No committed "queued" without a job behind it.
    assert status_of(aid) == ("completed", None)


def test_rerun_conflict_explains_the_state(client: TestClient) -> None:
    aid = make_analysis(status="processing", stage="transcribing", progress=40)
    r = client.post(f"/api/analyses/{aid}/rerun")
    assert r.status_code == 409
    assert "processing" in r.json()["detail"] and "transcribing" in r.json()["detail"]


def test_list_limit_validation(client: TestClient) -> None:
    assert client.get("/api/analyses?limit=-1").status_code == 422
    assert client.get("/api/analyses?limit=500").status_code == 422
    assert client.get("/api/analyses?limit=1&offset=0").status_code == 200


def test_readiness_probe(client: TestClient) -> None:
    r = client.get("/api/health/ready")
    assert r.status_code == 200, r.text
    assert r.json()["checks"]["database"] == "ok" and r.json()["checks"]["storage"] == "ok"


# ---------------------------------------------------------------- delete while processing


def test_delete_while_processing_leaves_no_files(monkeypatch: pytest.MonkeyPatch) -> None:
    aid = make_analysis(status="queued", stage="queued", storage_key=None)
    put_file(f"{analysis_prefix(aid)}/video.mp4")

    def pipeline_racing_a_delete(analysis_id: str) -> None:
        # The user deletes the analysis mid-run...
        with get_sessionmaker()() as db:
            a = db.get(Analysis, uuid.UUID(analysis_id))
            assert a is not None
            jobs.delete_analysis(db, a)
        # ...and the pipeline keeps writing frames / a working copy afterwards.
        put_file(f"{analysis_prefix(analysis_id)}/frames/F1.jpg")
        put_file(f"{analysis_prefix(analysis_id)}/working.mp4")

    monkeypatch.setattr(engine, "process_analysis", pipeline_racing_a_delete)
    jobs.enqueue_analysis(str(aid))  # inline in tests: runs run_analysis_job
    assert status_of(aid) is None
    assert not get_storage().local_path(analysis_prefix(aid)).exists()


def test_job_for_existing_analysis_keeps_its_files(monkeypatch: pytest.MonkeyPatch) -> None:
    aid = make_analysis()
    put_file(f"{analysis_prefix(aid)}/video.mp4")
    monkeypatch.setattr(engine, "process_analysis", lambda _id: None)
    jobs.run_analysis_job(str(aid))
    assert get_storage().local_path(f"{analysis_prefix(aid)}/video.mp4").exists()


# ---------------------------------------------------------------- orphans


def _age(path_key: str, seconds: float) -> None:
    root = get_storage().local_path(path_key)
    stamp = datetime.now(UTC).timestamp() - seconds
    for dirpath, dirnames, filenames in os.walk(root):
        for name in [*dirnames, *filenames]:
            os.utime(os.path.join(dirpath, name), (stamp, stamp))
    os.utime(root, (stamp, stamp))


def test_orphaned_storage_is_swept_after_grace() -> None:
    settings = get_settings()
    orphan = uuid.uuid4()
    recent_orphan = uuid.uuid4()
    owned = make_analysis()
    orphan_proof = uuid.uuid4()
    for aid in (orphan, recent_orphan, owned):
        put_file(f"{analysis_prefix(aid)}/frames/F1.jpg")
    put_file(f"rights/{orphan_proof}/proof.pdf")
    put_file("catalogue/incoming-abc.mp4")
    old = settings.orphan_grace_seconds + 60
    for key in (analysis_prefix(orphan), analysis_prefix(owned), f"rights/{orphan_proof}"):
        _age(key, old)
    stamp = datetime.now(UTC).timestamp() - old
    os.utime(get_storage().local_path("catalogue/incoming-abc.mp4"), (stamp, stamp))

    with get_sessionmaker()() as db:
        assert jobs.sweep_orphan_storage(db, settings) == 3
    storage = get_storage()
    assert not storage.exists(analysis_prefix(orphan))
    assert storage.exists(analysis_prefix(recent_orphan))  # may be an upload in progress
    assert storage.exists(analysis_prefix(owned))
    assert not storage.exists(f"rights/{orphan_proof}")
    assert not storage.exists("catalogue/incoming-abc.mp4")
    storage.delete_prefix(analysis_prefix(recent_orphan))


def test_rights_proof_with_a_record_is_kept() -> None:
    with get_sessionmaker()() as db:
        rec = RightsRecord(kind="music_license", counterparty="Label", match_terms=["Label"])
        db.add(rec)
        db.commit()
        rid = rec.id
    put_file(f"rights/{rid}/proof.pdf")
    _age(f"rights/{rid}", get_settings().orphan_grace_seconds + 60)
    with get_sessionmaker()() as db:
        jobs.sweep_orphan_storage(db, get_settings())
    assert get_storage().exists(f"rights/{rid}/proof.pdf")


# ---------------------------------------------------------------- scheduled purge


def test_scheduled_maintenance_purges_without_any_upload() -> None:
    expired = make_analysis(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    put_file(f"{analysis_prefix(expired)}/video.mp4")
    kept = make_analysis()
    with get_sessionmaker()() as db:
        db.add(
            MediaFingerprint(
                source="catalogue",
                owner_label="x",
                duration_seconds=1.0,
                sha256="0" * 64,
                frame_step=0.5,
                frame_hashes=[],
                audio_step=0.0,
                audio_fp=[],
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        db.commit()
    result = jobs.run_maintenance()
    assert result is not None and result["analyses_purged"] == 1
    assert status_of(expired) is None and status_of(kept) is not None
    assert not get_storage().exists(analysis_prefix(expired))
    with get_sessionmaker()() as db:
        assert db.query(MediaFingerprint).count() == 0


def test_maintenance_runs_are_exclusive() -> None:
    from sqlalchemy import text

    from app.db import get_engine

    with get_engine().connect() as other:
        assert other.execute(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": jobs.MAINTENANCE_LOCK_KEY}
        ).scalar()
        try:
            assert jobs.run_maintenance() is None  # another process holds the lock
        finally:
            other.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": jobs.MAINTENANCE_LOCK_KEY})
            other.commit()
    assert jobs.run_maintenance() is not None


# ---------------------------------------------------------------- paid lookups


def _lookup(aid: uuid.UUID | None, key: str, created: datetime | None = None) -> None:
    with get_sessionmaker()() as db:
        db.add(
            PaidLookup(
                service="music_id",
                provider="audd",
                units=1,
                est_cost_usd=0.01,
                cache_key=key,
                analysis_id=aid,
                response={"title": "Some Song", "frame": "private"},
                created_at=created or datetime.now(UTC),
            )
        )
        db.commit()


def test_deleting_an_analysis_detaches_its_paid_lookups() -> None:
    aid = make_analysis()
    other = make_analysis()
    _lookup(aid, "a" * 64)
    _lookup(other, "b" * 64)
    settings = get_settings()
    with get_sessionmaker()() as db:
        spent = budget.month_spend(db)
        a = db.get(Analysis, aid)
        assert a is not None
        jobs.delete_analysis(db, a)
    with get_sessionmaker()() as db:
        rows = {r.cache_key: r for r in db.query(PaidLookup).all()}
        assert jobs.PURGED_CACHE_KEY in rows and "a" * 64 not in rows
        detached = rows[jobs.PURGED_CACHE_KEY]
        assert detached.analysis_id is None and detached.response == {}
        assert rows["b" * 64].analysis_id == other
        # Not served from cache any more, but still counted against the budget.
        assert budget.cached(db, "a" * 64, settings) is None
        assert budget.month_spend(db) == pytest.approx(spent)


def test_retention_and_old_paid_lookups() -> None:
    aid = make_analysis(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    _lookup(aid, "c" * 64)
    _lookup(None, "d" * 64, created=datetime.now(UTC) - timedelta(days=90))
    with get_sessionmaker()() as db:
        jobs.purge_expired(db)
    with get_sessionmaker()() as db:
        rows = db.query(PaidLookup).all()
        assert [r.cache_key for r in rows] == [jobs.PURGED_CACHE_KEY]
        assert rows[0].analysis_id is None and rows[0].response == {}
