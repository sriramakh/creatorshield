from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import tempfile
from collections.abc import AsyncIterator, Awaitable, Callable, MutableMapping
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.connections import router as connections_router
from app.api.creator import router as creator_router
from app.api.provenance import router as provenance_router
from app.api.routes import router
from app.config import Settings, get_settings
from app.logging_config import configure_logging
from app.policies.kb import get_kb

log = logging.getLogger(__name__)

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

# Room for multipart boundaries and the form fields sent alongside a file.
MULTIPART_SLACK_BYTES = 1024 * 1024
_RIGHTS_PATH = re.compile(r"^/api/rights/?$")


class BodyTooLarge(Exception):
    pass


def body_limit_for(settings: Settings, method: str, path: str) -> int:
    """Largest request body accepted for this route (checked while it arrives)."""
    if method == "POST" and _RIGHTS_PATH.match(path):
        return settings.rights_proof_max_mb * 1024 * 1024 + MULTIPART_SLACK_BYTES
    return settings.max_upload_bytes + MULTIPART_SLACK_BYTES


class RequestBodyLimit:
    """Rejects oversized bodies with 413 before they are spooled to disk.

    Checks Content-Length up front, and counts bytes as they arrive for chunked
    or mis-declared bodies. Applies to every route, including uploads defined in
    other routers.
    """

    def __init__(self, app: Callable[[Scope, Receive, Send], Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            await self.app(scope, receive, send)
            return
        limit = body_limit_for(get_settings(), scope["method"], scope["path"])
        declared = None
        for name, value in scope.get("headers") or []:
            if name == b"content-length":
                declared = value
                break
        if declared is not None:
            try:
                too_big = int(declared) > limit
            except ValueError:
                await _send_json(send, 400, "Invalid Content-Length header.")
                return
            if too_big:
                await _send_json(send, 413, _too_large(limit))
                return

        received = 0
        exceeded = False
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    raise BodyTooLarge
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal response_started
            if exceeded:
                # Whatever the app made of the aborted body (usually a 400), answer 413.
                if message["type"] == "http.response.start" and not response_started:
                    response_started = True
                    await _send_json(send, 413, _too_large(limit))
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except BodyTooLarge:
            if not response_started:
                await _send_json(send, 413, _too_large(limit))


def _too_large(limit: int) -> str:
    mb = (limit - MULTIPART_SLACK_BYTES) / (1024 * 1024)
    size = f"{mb / 1024:g} GB" if mb >= 1024 else f"{mb:g} MB"
    return (
        f"Request too large (max {size}). Export or compress the video at 1080p first, "
        "e.g. with HandBrake's 'Fast 1080p30' preset."
    )


async def _send_json(send: Send, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"connection", b"close"),
                (b"cache-control", b"no-store"),
                (b"x-content-type-options", b"nosniff"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    from app.auth import verify_agency_database
    from app.jobs import maintenance_loop

    verify_agency_database(settings)
    configure_logging(settings.log_level)
    kb = get_kb(str(settings.policy_kb_path))  # fail fast on an invalid KB
    log.info(
        "CreatorShield API starting: env=%s provider=%s kb=%s (%d rules)",
        settings.app_env,
        settings.ai_provider,
        kb.version,
        len(kb.rules),
    )
    if not settings.ai_credentials_present():
        log.warning(
            "AI provider '%s' has no credentials configured; analyses will run "
            "rule-based checks only",
            settings.ai_provider,
        )
    stop = asyncio.Event()
    task = None
    if settings.maintenance_interval_seconds > 0:
        task = asyncio.create_task(maintenance_loop(settings.maintenance_interval_seconds, stop))
    try:
        yield
    finally:
        stop.set()
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.upload_tmp_dir is not None:
        # Multipart uploads spool here (on the media volume in containers).
        settings.upload_tmp_dir.mkdir(parents=True, exist_ok=True)
        tempfile.tempdir = str(settings.upload_tmp_dir)
    app = FastAPI(title="CreatorShield AI API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    # Inside authentication: unauthenticated requests are refused before any body is read.
    app.add_middleware(RequestBodyLimit)

    app.include_router(connections_router)
    app.include_router(creator_router)
    app.include_router(provenance_router)
    app.include_router(router)
    from app.auth import install_auth

    install_auth(app, settings)

    # Registered last, so it is the outermost layer and also covers 401/403/413/429.
    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    return app


app = create_app()
