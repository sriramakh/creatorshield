from __future__ import annotations

import json
import logging
import re
import shutil
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.analysis import caption_fix, market_disclosure, outcome
from app.analysis.brief import MAX_ITEM_CHARS as BRIEF_MAX_ITEM_CHARS
from app.analysis.brief import MAX_ITEMS as BRIEF_MAX_ITEMS
from app.analysis.deterministic import has_promo_signals
from app.api.creator import (
    available_markets,
    available_platforms,
    policy_refs,
    require_platform,
    resolve_brief,
    resolve_markets,
)
from app.config import get_settings
from app.db import get_db, get_engine
from app.jobs import delete_analysis, enqueue_analysis, get_redis
from app.media.probe import MediaError, probe, validate_duration, validate_extension
from app.models import Analysis, Finding
from app.policies.kb import get_kb
from app.reports.render import render_html, render_json
from app.reports.sections import section_for
from app.schemas import (
    CATEGORY_LABELS,
    AnalysisOut,
    AnalysisSummaryOut,
    CreateAnalysisOut,
    FindingOut,
    SponsorshipInput,
)
from app.storage import StorageError, analysis_prefix, get_storage

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

DB = Annotated[Session, Depends(get_db)]
LANGUAGES = {"en", "hi"}
MAX_CAPTION = 5000
MAX_HASHTAGS = 100
_HASHTAG_SPLIT = re.compile(r"[\s,]+")
_FRAME_ID = re.compile(r"^F\d{1,3}$")


def parse_hashtags(raw: str) -> list[str]:
    tags: list[str] = []
    for token in _HASHTAG_SPLIT.split(raw or ""):
        tag = token.strip().lstrip("#").strip()
        if tag and tag not in tags:
            tags.append(tag[:100])
    if len(tags) > MAX_HASHTAGS:
        raise HTTPException(422, f"At most {MAX_HASHTAGS} hashtags are accepted.")
    return tags


def _get(db: Session, analysis_id: uuid.UUID, *, lock: bool = False) -> Analysis:
    analysis = db.get(Analysis, analysis_id, with_for_update=lock)
    if analysis is None:
        raise HTTPException(404, "Analysis not found.")
    return analysis


def serialize(analysis: Analysis) -> AnalysisOut:
    findings: list[FindingOut] = []
    for f in analysis.findings:
        out = FindingOut.model_validate(f)
        out.category_label = CATEGORY_LABELS.get(f.category, f.category)
        out.report_section = section_for(f.category, list(f.policy_rule_ids))
        out.policies = policy_refs(list(f.policy_rule_ids))
        findings.append(out)
    data = AnalysisOut.model_validate(analysis, from_attributes=True)
    data.findings = findings
    data.finding_count = sum(1 for f in findings if f.finding_type != "cannot_check")
    data.markets = outcome.markets_of(analysis)
    if analysis.status == "completed":
        data.readiness = outcome.readiness_of(analysis)
        data.readiness_verdict = data.readiness["verdict"]
        data.market_disclosure = market_disclosure.assess(analysis.caption, data.markets)
        data.caption_fix = caption_fix.suggest(
            analysis.caption,
            list(analysis.hashtags or []),
            analysis.platform,
            data.markets,
            analysis.sponsorship,
            promo_detected=has_promo_signals(
                analysis.caption, list(analysis.hashtags or []), analysis.extraction or {}
            ),
        )
    return data


def current(db: Session, analysis: Analysis) -> Analysis:
    """Re-derive rights coverage before showing it, if the ledger or the date moved on."""
    if analysis.status == "completed":
        from app.provenance import pipeline

        if pipeline.ensure_current(db, analysis):
            db.commit()
            db.refresh(analysis)
    return analysis


def _json_object(raw: str, field: str) -> dict[str, Any] | None:
    """A JSON object sent as a multipart form field, or None when the field is empty."""
    if not raw.strip():
        return None
    try:
        value = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(422, f"{field} must be valid JSON.") from exc
    if not isinstance(value, dict):
        raise HTTPException(422, f"{field} must be a JSON object.")
    return value


def _uuid_or_none(raw: str) -> uuid.UUID | None:
    if not raw.strip():
        return None
    try:
        return uuid.UUID(raw.strip())
    except ValueError as exc:
        raise HTTPException(422, "brief_id must be a UUID.") from exc


def too_large_message(max_mb: int) -> str:
    size = f"{max_mb / 1024:g} GB" if max_mb >= 1024 else f"{max_mb} MB"
    return (
        f"File too large (max {size}). Export or compress it at 1080p first, e.g. with "
        "HandBrake's 'Fast 1080p30' preset; analysis never uses more than 1080p."
    )


@router.get("/health")
def health(db: DB) -> dict[str, Any]:
    settings = get_settings()
    checks: dict[str, Any] = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    try:
        get_redis().ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error" if settings.use_job_queue else "not_used"
    checks["ffmpeg"] = "ok" if shutil.which("ffmpeg") and shutil.which("ffprobe") else "missing"
    checks["tesseract"] = "ok" if shutil.which(settings.tesseract_cmd) else "missing"
    try:
        kb = get_kb(str(settings.policy_kb_path))
        checks["policy_kb"] = {"version": kb.version, "rules": len(kb.rules)}
    except Exception:
        checks["policy_kb"] = "error"
    ok = all(v in ("ok", "not_used") for k, v in checks.items() if k != "policy_kb")
    return {
        "status": "ok" if ok else "degraded",
        "checks": checks,
        "config": public_config(),
    }


@router.get("/health/live")
def health_live() -> dict[str, str]:
    """Liveness probe (no dependencies). Public so container healthchecks need no login."""
    return {"status": "ok"}


@router.get("/health/ready")
def health_ready(response: Response) -> dict[str, Any]:
    """Readiness probe: database, job queue and writable storage. 503 when not ready."""
    settings = get_settings()
    checks: dict[str, str] = {}
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    if settings.use_job_queue:
        try:
            get_redis().ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"
    try:
        root = get_storage().local_path("analyses").parent
        root.mkdir(parents=True, exist_ok=True)
        probe_file = root / f".ready-{uuid.uuid4().hex}"
        probe_file.write_bytes(b"ok")
        probe_file.unlink()
        checks["storage"] = "ok"
    except Exception:
        checks["storage"] = "error"
    ready = all(v == "ok" for v in checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready else "not_ready", "checks": checks}


def public_config() -> dict[str, Any]:
    """Non-secret configuration plus what the knowledge base makes available."""
    summary = get_settings().public_summary()
    summary["platforms"] = [p.public() for p in available_platforms().values()]
    summary["markets"] = [m.public() for m in available_markets().values()]
    summary["limits"] = {
        "caption_max": MAX_CAPTION,
        "hashtags_max": MAX_HASHTAGS,
        "sponsors_max": 10,
        "sponsor_name_max": 100,
        "brief_items_max": BRIEF_MAX_ITEMS,
        "brief_item_max": BRIEF_MAX_ITEM_CHARS,
    }
    return summary


@router.get("/config")
def config() -> dict[str, Any]:
    return public_config()


@router.get("/policies")
def policies() -> dict[str, Any]:
    kb = get_kb(str(get_settings().policy_kb_path))
    return kb.model_dump(mode="json")


@router.post("/analyses", status_code=status.HTTP_202_ACCEPTED)
def create_analysis(
    db: DB,
    file: Annotated[UploadFile, File()],
    platform: Annotated[str, Form()],
    language: Annotated[str, Form()],
    caption: Annotated[str, Form()] = "",
    hashtags: Annotated[str, Form()] = "",
    client_label: Annotated[str, Form(max_length=100)] = "",
    sponsorship: Annotated[str, Form(max_length=3000)] = "{}",
    markets: Annotated[str, Form(max_length=40)] = "",
    brief: Annotated[str, Form(max_length=20_000)] = "",
    brief_id: Annotated[str, Form(max_length=40)] = "",
) -> CreateAnalysisOut:
    settings = get_settings()
    require_platform(platform)
    if language not in LANGUAGES:
        raise HTTPException(422, "language must be en or hi.")
    if len(caption) > MAX_CAPTION:
        raise HTTPException(422, f"Caption must be at most {MAX_CAPTION} characters.")
    try:
        sponsor_context = SponsorshipInput.model_validate_json(sponsorship)
    except ValidationError as exc:
        raise HTTPException(422, "Invalid sponsorship details.") from exc
    tags = parse_hashtags(hashtags)
    try:
        ext, content_type = validate_extension(file.filename or "")
    except MediaError as exc:
        raise HTTPException(415, str(exc)) from exc
    chosen_markets = resolve_markets(db, [m for m in _HASHTAG_SPLIT.split(markets) if m])
    brief_spec = resolve_brief(db, _json_object(brief, "brief"), _uuid_or_none(brief_id))

    # Retention runs on a schedule (app.jobs.run_maintenance), not per upload.
    analysis_id = uuid.uuid4()
    storage = get_storage()
    prefix = analysis_prefix(analysis_id)
    key = f"{prefix}/video{ext}"
    try:
        size = storage.save_stream(key, file.file, settings.max_upload_bytes)
        # Free the spooled copy now rather than after the response.
        file.file.close()
        info = probe(storage.local_path(key))
        validate_duration(info, settings.max_duration_seconds, settings.duration_tolerance_seconds)
    except StorageError as exc:
        storage.delete_prefix(prefix)
        raise HTTPException(413, too_large_message(settings.max_upload_mb)) from exc
    except MediaError as exc:
        storage.delete_prefix(prefix)
        raise HTTPException(422, str(exc)) from exc

    analysis = Analysis(
        id=analysis_id,
        sponsorship=sponsor_context.model_dump(),
        markets=chosen_markets,
        brief=brief_spec.model_dump() if brief_spec else None,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.retention_hours),
        platform=platform,
        language=language,
        caption=caption,
        hashtags=tags,
        client_label=client_label.strip() or None,
        file_ext=ext,
        content_type=content_type,
        size_bytes=size,
        storage_key=key,
        duration_seconds=info.duration_seconds,
        media_info=info.to_dict(),
        status="queued",
        stage="queued",
        progress=5,
        limitations=[],
    )
    db.add(analysis)
    db.commit()
    try:
        enqueue_analysis(str(analysis_id))
    except Exception as exc:
        log.exception("failed to enqueue analysis")
        analysis.status, analysis.stage = "failed", "failed"
        analysis.error_message = "Could not queue the analysis (is Redis/the worker running?)."
        db.commit()
        raise HTTPException(503, analysis.error_message) from exc
    db.refresh(analysis)
    return CreateAnalysisOut(id=analysis.id, status=analysis.status)


@router.get("/analyses")
def list_analyses(
    db: DB,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> list[AnalysisSummaryOut]:
    rows = db.scalars(
        select(Analysis).order_by(Analysis.created_at.desc()).offset(offset).limit(limit)
    ).all()
    counts = dict(
        db.execute(
            select(Finding.analysis_id, func.count())
            .where(
                Finding.finding_type != "cannot_check",
                Finding.analysis_id.in_([a.id for a in rows]),
            )
            .group_by(Finding.analysis_id)
        ).all()
    )
    out = []
    for a in rows:
        s = AnalysisSummaryOut.model_validate(a, from_attributes=True)
        s.finding_count = counts.get(a.id, 0)
        out.append(s)
    return out


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: uuid.UUID, db: DB) -> AnalysisOut:
    return serialize(current(db, _get(db, analysis_id)))


@router.post("/analyses/{analysis_id}/rerun", status_code=status.HTTP_202_ACCEPTED)
def rerun_analysis(analysis_id: uuid.UUID, db: DB) -> CreateAnalysisOut:
    # Row lock: two reruns at once cannot both enqueue.
    analysis = _get(db, analysis_id, lock=True)
    if analysis.status in ("queued", "processing"):
        raise HTTPException(
            409,
            f"This analysis is already {analysis.status} (stage: {analysis.stage}, "
            f"{analysis.progress}%). Wait for it to finish; if it stops responding it is "
            "marked failed automatically and can be rerun then.",
        )
    if analysis.status == "awaiting_file":
        raise HTTPException(409, "Attach the original video file before running this analysis.")
    if analysis.source == "upload" and (analysis.media_deleted or not analysis.storage_key):
        raise HTTPException(
            409,
            "The video was deleted after analysis (retention or 'delete media after "
            "analysis'); upload it again to rerun.",
        )
    if analysis.source != "upload" and analysis.connection_id is None:
        raise HTTPException(409, "The connected account was removed; reconnect and import again.")
    previous = (analysis.status, analysis.stage, analysis.progress, analysis.error_message)
    analysis.status, analysis.stage, analysis.progress = "queued", "queued", 5
    analysis.error_message = None
    db.commit()
    try:
        enqueue_analysis(str(analysis.id))
    except Exception as exc:
        # Enqueue or roll back: never leave a "queued" analysis with no job behind it.
        log.exception("failed to enqueue rerun")
        (
            analysis.status,
            analysis.stage,
            analysis.progress,
            analysis.error_message,
        ) = previous
        db.commit()
        raise HTTPException(
            503, "Could not queue the analysis (is Redis/the worker running?). Try again."
        ) from exc
    return CreateAnalysisOut(id=analysis.id, status="queued")


@router.post("/analyses/{analysis_id}/owner-file", status_code=status.HTTP_202_ACCEPTED)
def attach_owner_file(
    analysis_id: uuid.UUID,
    db: DB,
    file: Annotated[UploadFile, File()],
) -> CreateAnalysisOut:
    """Store the creator's own file and review it against the published post.

    This does not download the platform's video. YouTube's API policies forbid
    that, and Instagram often withholds the file. The creator supplies the
    original they already have.
    """
    settings = get_settings()
    analysis = _get(db, analysis_id)
    if analysis.source not in {"instagram", "youtube"}:
        raise HTTPException(
            409,
            "Attach a file on an imported post. An uploaded video is already reviewed in full.",
        )
    if analysis.connection_id is None:
        raise HTTPException(409, "The connected account was removed; reconnect and import again.")
    if analysis.status in {"queued", "processing"}:
        raise HTTPException(409, "Analysis is already running.")
    try:
        ext, content_type = validate_extension(file.filename or "")
    except MediaError as exc:
        raise HTTPException(415, str(exc)) from exc

    storage = get_storage()
    prefix = analysis_prefix(analysis.id)
    # Unique name so two attaches at once cannot overwrite each other's upload.
    incoming = f"{prefix}/incoming-{uuid.uuid4().hex}{ext}"
    final = f"{prefix}/video{ext}"
    try:
        storage.save_stream(incoming, file.file, settings.max_upload_bytes)
        probe(storage.local_path(incoming))
    except StorageError as exc:
        storage.local_path(incoming).unlink(missing_ok=True)
        raise HTTPException(413, too_large_message(settings.max_upload_mb)) from exc
    except MediaError as exc:
        storage.local_path(incoming).unlink(missing_ok=True)
        raise HTTPException(422, str(exc)) from exc
    finally:
        file.file.close()

    # Re-check under a row lock: a rerun or another attach may have started meanwhile.
    locked = db.get(Analysis, analysis_id, with_for_update=True, populate_existing=True)
    if locked is None or locked.status in {"queued", "processing"}:
        storage.local_path(incoming).unlink(missing_ok=True)
        if locked is None:
            raise HTTPException(404, "Analysis not found.")
        raise HTTPException(409, "Analysis is already running.")
    analysis = locked
    final_path = storage.local_path(final)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    storage.local_path(incoming).replace(final_path)
    if analysis.storage_key and analysis.storage_key != final:
        previous = storage.local_path(analysis.storage_key)
        if previous.exists() and previous != final_path:
            previous.unlink()
    # Frames from an earlier run describe a different file; drop them now.
    storage.delete_prefix(f"{prefix}/frames")
    analysis.storage_key = final
    analysis.file_ext = ext
    analysis.content_type = content_type
    analysis.size_bytes = final_path.stat().st_size
    analysis.owner_supplied_media = True
    analysis.media_deleted = False
    analysis.status, analysis.stage, analysis.progress = "queued", "queued", 5
    analysis.error_message = None
    db.commit()
    try:
        enqueue_analysis(str(analysis.id))
    except Exception as exc:
        log.exception("failed to enqueue owner-file review")
        analysis.status, analysis.stage = "failed", "failed"
        analysis.error_message = "Could not queue the analysis (is Redis/the worker running?)."
        db.commit()
        raise HTTPException(503, analysis.error_message) from exc
    db.refresh(analysis)
    return CreateAnalysisOut(id=analysis.id, status=analysis.status)


@router.delete("/analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_analysis(analysis_id: uuid.UUID, db: DB) -> Response:
    delete_analysis(db, _get(db, analysis_id))
    return Response(status_code=204)


@router.get("/analyses/{analysis_id}/video")
def get_video(analysis_id: uuid.UUID, db: DB) -> FileResponse:
    analysis = _get(db, analysis_id)
    storage = get_storage()
    if not analysis.storage_key or not storage.exists(analysis.storage_key):
        raise HTTPException(404, "Video not available (deleted per retention settings).")
    return FileResponse(storage.local_path(analysis.storage_key), media_type=analysis.content_type)


@router.get("/analyses/{analysis_id}/frames/{frame_id}.jpg")
def get_frame(analysis_id: uuid.UUID, frame_id: str, db: DB) -> FileResponse:
    if not _FRAME_ID.match(frame_id):
        raise HTTPException(404, "Frame not found.")
    _get(db, analysis_id)
    storage = get_storage()
    key = f"{analysis_prefix(analysis_id)}/frames/{frame_id}.jpg"
    if not storage.exists(key):
        raise HTTPException(404, "Frame not found.")
    return FileResponse(storage.local_path(key), media_type="image/jpeg")


@router.get("/analyses/{analysis_id}/report.html")
def report_html(analysis_id: uuid.UUID, db: DB, download: bool = False) -> HTMLResponse:
    analysis = _get(db, analysis_id)
    if analysis.status != "completed":
        raise HTTPException(409, "Report is available once the analysis has completed.")
    headers = {"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"}
    if download:
        headers["Content-Disposition"] = (
            f'attachment; filename="creatorshield-report-{analysis_id}.html"'
        )
    return HTMLResponse(render_html(serialize(current(db, analysis))), headers=headers)


@router.get("/analyses/{analysis_id}/report.json")
def report_json(analysis_id: uuid.UUID, db: DB) -> JSONResponse:
    analysis = _get(db, analysis_id)
    if analysis.status != "completed":
        raise HTTPException(409, "Report is available once the analysis has completed.")
    return JSONResponse(
        render_json(serialize(current(db, analysis))),
        headers={
            "Content-Disposition": f'attachment; filename="creatorshield-report-{analysis_id}.json"'
        },
    )
