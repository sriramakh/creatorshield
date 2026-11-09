from __future__ import annotations

import logging
import re
import shutil
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.jobs import delete_analysis, enqueue_analysis, get_redis, purge_expired
from app.media.probe import MediaError, probe, validate_duration, validate_extension
from app.models import Analysis, Finding
from app.policies.kb import get_kb
from app.reports.render import render_html, render_json
from app.schemas import (
    CATEGORY_LABELS,
    AnalysisOut,
    AnalysisSummaryOut,
    CreateAnalysisOut,
    FindingOut,
    PolicyRef,
    SponsorshipInput,
)
from app.storage import StorageError, analysis_prefix, get_storage

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

DB = Annotated[Session, Depends(get_db)]
PLATFORMS = {"youtube_shorts", "instagram_reels"}
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


def _get(db: Session, analysis_id: uuid.UUID) -> Analysis:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(404, "Analysis not found.")
    return analysis


def serialize(analysis: Analysis) -> AnalysisOut:
    kb = get_kb(str(get_settings().policy_kb_path))
    findings: list[FindingOut] = []
    for f in analysis.findings:
        out = FindingOut.model_validate(f)
        out.category_label = CATEGORY_LABELS.get(f.category, f.category)
        for rid in f.policy_rule_ids:
            rule = kb.get(rid)
            if rule:
                out.policies.append(
                    PolicyRef(
                        id=rule.id,
                        platform=rule.platform,
                        title=rule.title,
                        official_title=rule.official_title,
                        official_url=str(rule.official_url),
                        verified_on=rule.verified_on.isoformat(),
                    )
                )
        findings.append(out)
    data = AnalysisOut.model_validate(analysis, from_attributes=True)
    data.findings = findings
    data.finding_count = sum(1 for f in findings if f.finding_type != "cannot_check")
    return data


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
        "config": settings.public_summary(),
    }


@router.get("/config")
def config() -> dict[str, Any]:
    return get_settings().public_summary()


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
) -> CreateAnalysisOut:
    settings = get_settings()
    if platform not in PLATFORMS:
        raise HTTPException(422, "platform must be youtube_shorts or instagram_reels.")
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

    purge_expired(db)
    analysis_id = uuid.uuid4()
    storage = get_storage()
    prefix = analysis_prefix(analysis_id)
    key = f"{prefix}/video{ext}"
    try:
        size = storage.save_stream(key, file.file, settings.max_upload_bytes)
        info = probe(storage.local_path(key))
        validate_duration(info, settings.max_duration_seconds, settings.duration_tolerance_seconds)
    except StorageError as exc:
        storage.delete_prefix(prefix)
        raise HTTPException(413, f"File too large (max {settings.max_upload_mb} MB).") from exc
    except MediaError as exc:
        storage.delete_prefix(prefix)
        raise HTTPException(422, str(exc)) from exc

    analysis = Analysis(
        id=analysis_id,
        sponsorship=sponsor_context.model_dump(),
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
def list_analyses(db: DB, limit: int = 50) -> list[AnalysisSummaryOut]:
    rows = db.scalars(
        select(Analysis).order_by(Analysis.created_at.desc()).limit(min(limit, 200))
    ).all()
    counts = dict(
        db.execute(
            select(Finding.analysis_id, func.count())
            .where(Finding.finding_type != "cannot_check")
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
    return serialize(_get(db, analysis_id))


@router.post("/analyses/{analysis_id}/rerun", status_code=status.HTTP_202_ACCEPTED)
def rerun_analysis(analysis_id: uuid.UUID, db: DB) -> CreateAnalysisOut:
    analysis = _get(db, analysis_id)
    if analysis.status in ("queued", "processing"):
        raise HTTPException(409, "Analysis is already running.")
    if analysis.source == "upload" and (analysis.media_deleted or not analysis.storage_key):
        raise HTTPException(409, "The video was deleted after analysis; upload it again.")
    if analysis.status == "awaiting_file":
        raise HTTPException(409, "Attach the original video file before running this analysis.")
    if analysis.source != "upload" and analysis.connection_id is None:
        raise HTTPException(409, "The connected account was removed; reconnect and import again.")
    analysis.status, analysis.stage, analysis.progress = "queued", "queued", 5
    analysis.error_message = None
    db.commit()
    enqueue_analysis(str(analysis.id))
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
        raise HTTPException(413, f"File too large (max {settings.max_upload_mb} MB).") from exc
    except MediaError as exc:
        storage.local_path(incoming).unlink(missing_ok=True)
        raise HTTPException(422, str(exc)) from exc

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
    return HTMLResponse(render_html(serialize(analysis)), headers=headers)


@router.get("/analyses/{analysis_id}/report.json")
def report_json(analysis_id: uuid.UUID, db: DB) -> JSONResponse:
    analysis = _get(db, analysis_id)
    if analysis.status != "completed":
        raise HTTPException(409, "Report is available once the analysis has completed.")
    return JSONResponse(
        render_json(serialize(analysis)),
        headers={
            "Content-Disposition": f'attachment; filename="creatorshield-report-{analysis_id}.json"'
        },
    )
