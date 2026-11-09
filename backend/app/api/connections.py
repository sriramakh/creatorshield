"""Connected accounts (official OAuth) and importing your own posts for analysis."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.integrations import youtube as yt
from app.integrations.common import IntegrationError
from app.integrations.connections import (
    PLATFORMS,
    complete_authorization,
    disconnect,
    list_media,
    resolve_media,
    start_authorization,
)
from app.jobs import enqueue_analysis, purge_expired
from app.models import Analysis, PlatformConnection
from app.schemas import ConnectionOut, CreateAnalysisOut, ImportRequest

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")
DB = Annotated[Session, Depends(get_db)]

TARGET_PLATFORM = {"instagram": "instagram_reels", "youtube": "youtube_shorts"}
# Only these fixed codes are ever reflected back to the frontend.
CALLBACK_ERRORS = {"denied", "failed", "state", "not_configured"}


def _http_error(exc: IntegrationError) -> HTTPException:
    return HTTPException(exc.status_code, exc.user_message)


def _out(conn: PlatformConnection) -> ConnectionOut:
    out = ConnectionOut.model_validate(conn)
    out.captions_enabled = conn.platform == "youtube" and yt.SCOPE_CAPTIONS in conn.scopes
    return out


def _get_conn(db: Session, connection_id: uuid.UUID) -> PlatformConnection:
    conn = db.get(PlatformConnection, connection_id)
    if conn is None:
        raise HTTPException(404, "Connection not found.")
    return conn


@router.get("/connections")
def list_connections(db: DB) -> dict[str, Any]:
    settings = get_settings()
    rows = db.scalars(select(PlatformConnection).order_by(PlatformConnection.created_at)).all()
    return {
        "encryption_configured": bool(
            settings.token_encryption_key and settings.token_encryption_key.get_secret_value()
        ),
        "instagram": {
            "configured": settings.instagram_configured,
            "redirect_uri": settings.instagram_callback,
            "connections": [_out(c) for c in rows if c.platform == "instagram"],
        },
        "youtube": {
            "configured": settings.youtube_configured,
            "redirect_uri": settings.youtube_callback,
            "captions_scope": settings.youtube_captions_scope,
            "connections": [_out(c) for c in rows if c.platform == "youtube"],
        },
    }


@router.post("/connections/{platform}/authorize")
def authorize(platform: str) -> dict[str, str]:
    if platform not in PLATFORMS:
        raise HTTPException(404, "Unknown platform.")
    try:
        return {"authorization_url": start_authorization(platform, get_settings())}
    except IntegrationError as exc:
        raise _http_error(exc) from exc


@router.get("/connections/{platform}/callback", include_in_schema=False)
def oauth_callback(
    platform: str,
    db: DB,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    settings = get_settings()
    base = f"{settings.frontend_url.rstrip('/')}/connections"

    def back(**params: str) -> RedirectResponse:
        return RedirectResponse(f"{base}?{urlencode(params)}", status_code=303)

    if platform not in PLATFORMS:
        return back(error="failed")
    if error or not code:
        return back(error="denied", platform=platform)
    try:
        conn = complete_authorization(db, platform, code, state or "", settings)
    except IntegrationError as exc:
        log.warning("OAuth callback failed for %s: %s", platform, exc.user_message)
        code_ = "state" if "state" in exc.user_message.lower() else "failed"
        if exc.status_code == 503:
            code_ = "not_configured"
        return back(error=code_ if code_ in CALLBACK_ERRORS else "failed", platform=platform)
    return back(connected=platform, id=str(conn.id))


@router.delete("/connections/{connection_id}")
def remove_connection(connection_id: uuid.UUID, db: DB) -> dict[str, int]:
    conn = _get_conn(db, connection_id)
    deleted = disconnect(db, conn, get_settings())
    return {"deleted_analyses": deleted}


@router.get("/connections/{connection_id}/media")
def connection_media(connection_id: uuid.UUID, db: DB, cursor: str | None = None) -> dict[str, Any]:
    conn = _get_conn(db, connection_id)
    if cursor is not None and len(cursor) > 300:
        raise HTTPException(422, "Invalid cursor.")
    try:
        items, nxt = list_media(db, conn, get_settings(), cursor)
    except IntegrationError as exc:
        raise _http_error(exc) from exc
    return {"items": items, "next_cursor": nxt}


@router.post("/analyses/import", status_code=status.HTTP_202_ACCEPTED)
def import_analysis(body: ImportRequest, db: DB) -> CreateAnalysisOut:
    settings = get_settings()
    conn = _get_conn(db, body.connection_id)
    try:
        media = resolve_media(db, conn, settings, url=body.url, media_id=body.media_id)
    except IntegrationError as exc:
        raise _http_error(exc) from exc

    purge_expired(db)
    hours = settings.retention_hours
    if conn.platform == "youtube":
        hours = min(hours, settings.youtube_max_retention_hours)
    waiting = body.attach_owner_file
    analysis = Analysis(
        expires_at=datetime.now(UTC) + timedelta(hours=hours),
        platform=TARGET_PLATFORM[conn.platform],
        language=body.language,
        caption=media.get("caption") or "",
        hashtags=[],
        file_ext="",
        content_type="",
        size_bytes=0,
        storage_key=None,
        source=conn.platform,
        analysis_mode=media["expected_mode"],
        connection_id=conn.id,
        source_media_id=str(media["id"]),
        source_url=media.get("permalink"),
        source_title=(media.get("title") or "")[:300],
        duration_seconds=media.get("duration_seconds"),
        client_label=(body.client_label or "").strip()[:100] or None,
        status="awaiting_file" if waiting else "queued",
        stage="awaiting_file" if waiting else "queued",
        progress=0 if waiting else 3,
        limitations=[],
    )
    db.add(analysis)
    db.commit()
    if waiting:
        return CreateAnalysisOut(id=analysis.id, status="awaiting_file")
    try:
        enqueue_analysis(str(analysis.id))
    except Exception as exc:
        log.exception("failed to enqueue import")
        analysis.status, analysis.stage = "failed", "failed"
        analysis.error_message = "Could not queue the analysis (is Redis/the worker running?)."
        db.commit()
        raise HTTPException(503, analysis.error_message) from exc
    db.refresh(analysis)
    return CreateAnalysisOut(id=analysis.id, status=analysis.status)
