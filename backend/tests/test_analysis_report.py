"""Report HTML: locked down when saved or zipped, and safe links only."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.reports.render import render_html, safe_href
from app.schemas import AnalysisOut


def _analysis(**overrides: Any) -> AnalysisOut:
    now = datetime.now(UTC)
    data: dict[str, Any] = dict(
        id=uuid.uuid4(),
        created_at=now,
        updated_at=now,
        expires_at=now,
        status="completed",
        stage="completed",
        progress=100,
        platform="instagram_reels",
        language="en",
        caption="",
        duration_seconds=None,
        risk_level="low",
        risk_score=0,
        mock_mode=False,
        source="instagram",
        error_message=None,
        hashtags=[],
        file_ext="jpg",
        content_type="image/jpeg",
        size_bytes=0,
        media_deleted=False,
        media_info=None,
        extraction=None,
        ai_provider=None,
        ai_model=None,
        ai_status="skipped",
        ai_status_detail=None,
        policy_kb_version="2026.11.26",
        summary="<script>alert(1)</script>",
        context_assessment=None,
        limitations=[],
        findings=[],
    )
    data.update(overrides)
    return AnalysisOut.model_validate(data)


def test_report_carries_its_own_csp_for_saved_and_zipped_copies() -> None:
    html = render_html(_analysis())
    assert '<meta http-equiv="Content-Security-Policy"' in html
    assert "default-src 'none'" in html
    # Model and user text is escaped, never markup.
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        " javascript:alert(1)",
        "data:text/html,<b>x</b>",
        "vbscript:msgbox(1)",
        "//evil.example/x",
        "https:/no-host",
    ],
)
def test_non_http_source_url_is_not_a_link(url: str) -> None:
    assert safe_href(url) is None
    html = render_html(_analysis(source_url=url))
    assert 'href="javascript' not in html.lower()
    assert 'href="data:' not in html
    assert "<a href" not in html.split("Language:")[1].split("</p>")[0]


def test_http_source_url_is_linked() -> None:
    url = "https://www.instagram.com/reel/ABC123/"
    assert safe_href(url) == url
    html = render_html(_analysis(source_url=url))
    assert f'<a href="{url}" rel="noopener noreferrer">' in html
