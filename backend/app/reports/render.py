"""Compliance report rendering (self-contained HTML + JSON)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import markets as market_registry
from app.platforms import PLATFORM_NAMES
from app.reports.sections import section_for
from app.schemas import AnalysisOut

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)

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


def safe_href(url: object) -> str | None:
    """The URL if it is an absolute http(s) link, else None (no javascript:, data: ...)."""
    if not isinstance(url, str):
        return None
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return None
    return url.strip()


_env.filters["ts"] = fmt_time
_env.filters["safe_href"] = safe_href


def render_html(analysis: AnalysisOut) -> str:
    template = _env.get_template("report.html.j2")
    for finding in analysis.findings:
        finding.report_section = section_for(finding.category, list(finding.policy_rule_ids))
    actionable = [f for f in analysis.findings if f.finding_type != "cannot_check"]
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
        actionable=actionable,
        community=[f for f in actionable if f.report_section == "community"],
        brief=[f for f in actionable if f.report_section == "brief"],
        market_names=[
            f"{market_registry.MARKETS[m].label} ({market_registry.MARKETS[m].regulator})"
            for m in analysis.markets
            if m in market_registry.MARKETS
        ],
        disclosure=[f for f in actionable if f.report_section == "disclosure"],
        other=[f for f in actionable if f.report_section == "other"],
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
