from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.connections import router as connections_router
from app.api.provenance import router as provenance_router
from app.api.routes import router
from app.config import get_settings
from app.logging_config import configure_logging
from app.policies.kb import get_kb

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
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
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="CreatorShield AI API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    app.include_router(connections_router)
    app.include_router(provenance_router)
    app.include_router(router)
    return app


app = create_app()
