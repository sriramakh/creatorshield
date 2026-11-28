"""Engine fallbacks: AI and platform failures must not cost the rule-based report.

Database-backed (uses the conftest Postgres fixtures); no media processing.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from app.analysis import engine
from app.db import get_sessionmaker
from app.models import Analysis


def _imported_analysis(caption: str) -> uuid.UUID:
    db = get_sessionmaker()()
    try:
        row = Analysis(
            expires_at=datetime.now(UTC) + timedelta(days=1),
            platform="instagram_reels",
            language="en",
            caption=caption,
            hashtags=[],
            file_ext="jpg",
            content_type="image/jpeg",
            size_bytes=0,
            source="instagram",
            analysis_mode="caption_thumbnail",
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def _load(aid: uuid.UUID) -> Analysis:
    db = get_sessionmaker()()
    try:
        row = db.get(Analysis, aid)
        assert row is not None
        db.expunge(row)
        return row
    finally:
        db.close()


def _prebuilt(*_: Any) -> dict[str, Any]:
    return {"transcript": {"segments": []}, "frames": [], "ocr": []}


@pytest.mark.parametrize("error", [RuntimeError("sdk blew up"), KeyError("choices")])
def test_any_ai_exception_falls_back_to_rule_based_results(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    class Broken:
        name, model = "openai", "gpt-5"

        def analyze(self, payload: object) -> None:
            raise error

    monkeypatch.setattr(engine, "prepare_import", _prebuilt)
    monkeypatch.setattr(engine, "get_provider", lambda settings: Broken())
    aid = _imported_analysis("Use code GLOW20 for 20% off")
    engine.process_analysis(str(aid))
    a = _load(aid)
    assert a.status == "completed"
    assert a.ai_status == "failed" and a.ai_status_detail == engine.AI_UNEXPECTED_FAILURE
    assert a.limitations and a.limitations[0].startswith("AI review was not performed")


def test_platform_network_error_fails_with_a_clear_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unreachable(*_: Any) -> dict[str, Any]:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(engine, "prepare_import", unreachable)
    aid = _imported_analysis("caption")
    engine.process_analysis(str(aid))
    a = _load(aid)
    assert a.status == "failed"
    assert a.error_message == engine.PLATFORM_UNREACHABLE
