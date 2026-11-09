"""Rights ledger, catalogue, provenance lookups and the evidence pack."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.media.probe import MediaError, probe, validate_extension
from app.models import Analysis, MediaFingerprint, RightsRecord
from app.provenance import budget, catalogue, evidence_pack, pipeline, youtube_search
from app.provenance.common import LookupFailed
from app.provenance.fingerprint import compute_fingerprint
from app.provenance.ledger import KINDS
from app.reports.render import render_html
from app.storage import StorageError, get_storage

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")
DB = Annotated[Session, Depends(get_db)]

PLATFORM_KEYS = {"youtube", "instagram"}
_PROOF_TYPES = {
    b"%PDF": ("application/pdf", ".pdf"),
    b"\x89PNG": ("image/png", ".png"),
    b"\xff\xd8\xff": ("image/jpeg", ".jpg"),
}
_SPLIT = re.compile(r"[\n,]+")
REBUILD_LIMIT = 200


# --------------------------------------------------------------------------- schemas


class RightsRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    kind: str
    kind_label: str = ""
    counterparty: str
    match_terms: list[str]
    platforms: list[str]
    client_label: str | None
    valid_from: date | None
    valid_until: date | None
    reference: str
    notes: str
    has_proof: bool = False
    status: str = "active"


class FingerprintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    source: str
    analysis_id: uuid.UUID | None
    owner_label: str
    platform: str | None
    title: str | None
    duration_seconds: float
    frames_hashed: int = 0
    has_audio: bool = False


class YouTubeLookupIn(BaseModel):
    query: str = Field(min_length=3, max_length=120)


def _record_out(rec: RightsRecord) -> RightsRecordOut:
    out = RightsRecordOut.model_validate(rec)
    out.kind_label = KINDS.get(rec.kind, rec.kind)
    out.has_proof = bool(rec.proof_key)
    today = date.today()
    if rec.valid_from and today < rec.valid_from:
        out.status = "not_started"
    elif rec.valid_until and today > rec.valid_until:
        out.status = "expired"
    return out


def _fingerprint_out(row: MediaFingerprint) -> FingerprintOut:
    out = FingerprintOut.model_validate(row)
    out.frames_hashed = sum(1 for h in row.frame_hashes or [] if h is not None)
    out.has_audio = bool(row.audio_fp)
    return out


def _terms(raw: str) -> list[str]:
    out: list[str] = []
    for part in _SPLIT.split(raw or ""):
        term = part.strip()[:100]
        if term and term.casefold() not in {t.casefold() for t in out}:
            out.append(term)
    if len(out) > 20:
        raise HTTPException(422, "At most 20 match terms per record.")
    return out


def _date(raw: str | None, field: str) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(422, f"{field} must be a date (YYYY-MM-DD).") from exc


def _rebuild_all(db: Session) -> int:
    """Re-derive rights coverage on completed analyses after a ledger change."""
    rows = db.scalars(
        select(Analysis)
        .where(Analysis.status == "completed", Analysis.provenance.is_not(None))
        .order_by(Analysis.created_at.desc())
        .limit(REBUILD_LIMIT)
    ).all()
    for analysis in rows:
        pipeline.rebuild(db, analysis)
    return len(rows)


def _analysis(db: Session, analysis_id: uuid.UUID) -> Analysis:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(404, "Analysis not found.")
    if analysis.status != "completed":
        raise HTTPException(409, "Available once the analysis has completed.")
    return analysis


# --------------------------------------------------------------------------- status


@router.get("/provenance/status")
def provenance_status(db: DB) -> dict[str, Any]:
    settings = get_settings()
    return {
        "music_id": {
            "provider": settings.music_id_provider,
            "configured": settings.music_id_configured,
            "auto": settings.music_id_auto,
            "est_cost_per_call_usd": settings.audd_cost_per_request_usd,
        },
        "web_detection": {
            "provider": settings.web_detection_provider,
            "configured": settings.web_detection_configured,
            "auto": settings.web_detection_auto,
            "est_cost_per_image_usd": settings.web_detection_cost_per_image_usd,
            "max_frames": settings.web_detection_max_frames,
        },
        "youtube_search": {
            "available": settings.public_summary()["youtube_search_available"],
            "units_per_search": youtube_search.SEARCH_COST_UNITS,
            "units_used_today": youtube_search.quota_used(),
            "daily_unit_cap": settings.youtube_search_daily_unit_cap,
        },
        "budget": budget.status(db, settings),
        "catalogue": {
            "entries": db.query(MediaFingerprint).count(),
            "retention_days": settings.catalogue_retention_days,
        },
    }


# --------------------------------------------------------------------------- rights ledger


@router.get("/rights")
def list_rights(db: DB) -> list[RightsRecordOut]:
    rows = db.scalars(select(RightsRecord).order_by(RightsRecord.created_at.desc())).all()
    return [_record_out(r) for r in rows]


@router.post("/rights", status_code=status.HTTP_201_CREATED)
def create_right(
    db: DB,
    kind: Annotated[str, Form()],
    counterparty: Annotated[str, Form(max_length=200)],
    match_terms: Annotated[str, Form(max_length=2000)] = "",
    platforms: Annotated[str, Form(max_length=40)] = "",
    client_label: Annotated[str, Form(max_length=100)] = "",
    valid_from: Annotated[str, Form(max_length=10)] = "",
    valid_until: Annotated[str, Form(max_length=10)] = "",
    reference: Annotated[str, Form(max_length=300)] = "",
    notes: Annotated[str, Form(max_length=2000)] = "",
    proof: Annotated[UploadFile | None, File()] = None,
) -> RightsRecordOut:
    settings = get_settings()
    if kind not in KINDS:
        raise HTTPException(422, f"kind must be one of: {', '.join(KINDS)}.")
    counterparty = counterparty.strip()
    if not counterparty:
        raise HTTPException(422, "Name the account, brand, label or licensor.")
    plats = [p.strip().lower() for p in platforms.split(",") if p.strip()]
    if any(p not in PLATFORM_KEYS for p in plats):
        raise HTTPException(422, "platforms may contain youtube and/or instagram.")
    start, end = _date(valid_from, "valid_from"), _date(valid_until, "valid_until")
    if start and end and end < start:
        raise HTTPException(422, "valid_until is before valid_from.")
    rec = RightsRecord(
        kind=kind,
        counterparty=counterparty,
        match_terms=_terms(match_terms) or [counterparty],
        platforms=plats,
        client_label=client_label.strip() or None,
        valid_from=start,
        valid_until=end,
        reference=reference.strip(),
        notes=notes.strip(),
    )
    db.add(rec)
    db.flush()
    if proof is not None and proof.filename:
        head = proof.file.read(8)
        proof.file.seek(0)
        kind_ext = next((v for k, v in _PROOF_TYPES.items() if head.startswith(k)), None)
        if kind_ext is None:
            db.rollback()
            raise HTTPException(415, "Proof must be a PDF, PNG or JPEG file.")
        key = f"rights/{rec.id}/proof{kind_ext[1]}"
        try:
            get_storage().save_stream(key, proof.file, settings.rights_proof_max_mb * 1024 * 1024)
        except StorageError as exc:
            db.rollback()
            raise HTTPException(
                413, f"Proof file too large (max {settings.rights_proof_max_mb} MB)."
            ) from exc
        rec.proof_key, rec.proof_content_type = key, kind_ext[0]
    db.commit()
    _rebuild_all(db)
    db.refresh(rec)
    return _record_out(rec)


@router.delete("/rights/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_right(record_id: uuid.UUID, db: DB) -> Response:
    rec = db.get(RightsRecord, record_id)
    if rec is None:
        raise HTTPException(404, "Record not found.")
    get_storage().delete_prefix(f"rights/{rec.id}")
    db.delete(rec)
    db.commit()
    _rebuild_all(db)
    return Response(status_code=204)


@router.get("/rights/{record_id}/proof")
def get_proof(record_id: uuid.UUID, db: DB) -> FileResponse:
    rec = db.get(RightsRecord, record_id)
    storage = get_storage()
    if rec is None or not rec.proof_key or not storage.exists(rec.proof_key):
        raise HTTPException(404, "No proof file for this record.")
    return FileResponse(
        storage.local_path(rec.proof_key),
        media_type=rec.proof_content_type or "application/octet-stream",
        headers={"Content-Disposition": "attachment"},
    )


# --------------------------------------------------------------------------- catalogue


@router.get("/catalogue")
def list_catalogue(db: DB, limit: int = 200) -> list[FingerprintOut]:
    rows = db.scalars(
        select(MediaFingerprint)
        .order_by(MediaFingerprint.created_at.desc())
        .limit(min(max(limit, 1), 1000))
    ).all()
    return [_fingerprint_out(r) for r in rows]


@router.post("/catalogue", status_code=status.HTTP_201_CREATED)
def add_to_catalogue(
    db: DB,
    file: Annotated[UploadFile, File()],
    owner_label: Annotated[str, Form(min_length=1, max_length=100)],
    platform: Annotated[str, Form(max_length=32)] = "",
    title: Annotated[str, Form(max_length=300)] = "",
) -> dict[str, Any]:
    """Fingerprint a past post (no AI, no paid calls) and discard the file."""
    settings = get_settings()
    if platform and platform not in {"youtube_shorts", "instagram_reels"}:
        raise HTTPException(422, "platform must be youtube_shorts or instagram_reels.")
    try:
        ext, _ = validate_extension(file.filename or "")
    except MediaError as exc:
        raise HTTPException(415, str(exc)) from exc
    storage = get_storage()
    key = f"catalogue/incoming-{uuid.uuid4().hex}{ext}"
    try:
        storage.save_stream(key, file.file, settings.max_upload_bytes)
        path = storage.local_path(key)
        info = probe(path)
        fp = compute_fingerprint(
            path, info.duration_seconds, settings.catalogue_max_seconds, settings.fpcalc_cmd
        )
    except StorageError as exc:
        raise HTTPException(413, f"File too large (max {settings.max_upload_mb} MB).") from exc
    except MediaError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        storage.delete_prefix(key)
    label = owner_label.strip()
    existing = db.scalars(
        select(MediaFingerprint).where(
            MediaFingerprint.sha256 == fp.sha256, MediaFingerprint.source == "catalogue"
        )
    ).first()
    if existing is not None and existing.owner_label.casefold() == label.casefold():
        return {"duplicate": True, "entry": _fingerprint_out(existing)}
    row = MediaFingerprint(
        source="catalogue",
        owner_label=label,
        platform=platform or None,
        title=title.strip() or None,
        duration_seconds=fp.duration_seconds,
        sha256=fp.sha256,
        frame_step=fp.frame_step,
        frame_hashes=fp.frame_hashes,
        audio_step=fp.audio_step,
        audio_fp=fp.audio_fp,
        expires_at=catalogue.fingerprint_expiry("catalogue", settings),
    )
    db.add(row)
    db.commit()
    return {
        "duplicate": False,
        "entry": _fingerprint_out(row),
        "truncated": info.duration_seconds > settings.catalogue_max_seconds,
    }


@router.delete("/catalogue/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_catalogue_entry(entry_id: uuid.UUID, db: DB) -> Response:
    row = db.get(MediaFingerprint, entry_id)
    if row is None:
        raise HTTPException(404, "Catalogue entry not found.")
    db.delete(row)
    db.commit()
    return Response(status_code=204)


# --------------------------------------------------------------------------- lookups


def _lookup_error(exc: LookupFailed) -> HTTPException:
    return HTTPException(409, exc.user_message)


@router.post("/analyses/{analysis_id}/lookups/web")
def lookup_web(analysis_id: uuid.UUID, db: DB) -> dict[str, Any]:
    analysis = _analysis(db, analysis_id)
    try:
        return pipeline.lookup_web(db, analysis, get_settings())
    except LookupFailed as exc:
        raise _lookup_error(exc) from exc


@router.post("/analyses/{analysis_id}/lookups/music")
def lookup_music(analysis_id: uuid.UUID, db: DB) -> dict[str, Any]:
    analysis = _analysis(db, analysis_id)
    try:
        return pipeline.lookup_music(db, analysis, get_settings())
    except LookupFailed as exc:
        raise _lookup_error(exc) from exc


@router.get("/analyses/{analysis_id}/lookups/youtube/suggest")
def suggest_youtube(analysis_id: uuid.UUID, db: DB) -> dict[str, Any]:
    analysis = _analysis(db, analysis_id)
    settings = get_settings()
    return {
        "query": pipeline.suggested_query(analysis),
        "units_per_search": youtube_search.SEARCH_COST_UNITS,
        "units_used_today": youtube_search.quota_used(),
        "daily_unit_cap": settings.youtube_search_daily_unit_cap,
    }


@router.post("/analyses/{analysis_id}/lookups/youtube")
def lookup_youtube(analysis_id: uuid.UUID, body: YouTubeLookupIn, db: DB) -> dict[str, Any]:
    analysis = _analysis(db, analysis_id)
    try:
        return pipeline.lookup_youtube(db, analysis, body.query, get_settings())
    except LookupFailed as exc:
        raise _lookup_error(exc) from exc


@router.post("/analyses/{analysis_id}/recheck-rights")
def recheck_rights(analysis_id: uuid.UUID, db: DB) -> dict[str, Any]:
    analysis = _analysis(db, analysis_id)
    pipeline.rebuild(db, analysis)
    return {"rights": (analysis.provenance or {}).get("rights", [])}


@router.get("/analyses/{analysis_id}/evidence-pack.zip")
def evidence_pack_zip(analysis_id: uuid.UUID, db: DB) -> Response:
    from app.api.routes import serialize

    analysis = _analysis(db, analysis_id)
    data = evidence_pack.build_zip(db, analysis, render_html(serialize(analysis)))
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return Response(
        data,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="creatorshield-evidence-{analysis_id}-{stamp}.zip"'
            )
        },
    )
