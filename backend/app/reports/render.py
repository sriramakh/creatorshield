"""Compliance report rendering (self-contained HTML + JSON)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.schemas import AnalysisOut

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)

PLATFORM_NAMES = {"youtube_shorts": "YouTube Shorts", "instagram_reels": "Instagram Reels"}
LANGUAGE_NAMES = {"en": "English", "hi": "Hindi"}
TYPE_LABELS = {
    "observed_evidence": "Observed evidence",
    "suspected_violation": "Suspected issue",
    "licensing_uncertainty": "Licensing uncertainty",
    "cannot_check": "Cannot be checked",
}


def fmt_time(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    m, s = divmod(seconds, 60)
    return f"{int(m)}:{s:04.1f}"


_env.filters["ts"] = fmt_time


def render_html(analysis: AnalysisOut) -> str:
    template = _env.get_template("report.html.j2")
    return template.render(
        a=analysis,
        platform_name=PLATFORM_NAMES.get(analysis.platform, analysis.platform),
        language_name=LANGUAGE_NAMES.get(analysis.language, analysis.language),
        source_name={
            "upload": "Uploaded file",
            "instagram": "Instagram import",
            "youtube": "YouTube import",
        }.get(analysis.source, analysis.source),
        type_labels=TYPE_LABELS,
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        actionable=[f for f in analysis.findings if f.finding_type != "cannot_check"],
        cannot_check=[f for f in analysis.findings if f.finding_type == "cannot_check"],
    )


def render_json(analysis: AnalysisOut) -> dict[str, Any]:
    data = analysis.model_dump(mode="json")
    data["report_generated_at"] = datetime.now(UTC).isoformat()
    data["disclaimer"] = (
        "Heuristic pre-publication review. Not legal advice. Does not guarantee platform "
        "enforcement outcomes. Risk score is not a probability of removal or suspension."
    )
    return data
