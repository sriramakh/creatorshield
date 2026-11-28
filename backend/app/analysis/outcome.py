"""What a review concluded: the readiness verdict and the stats row for insights.

Called whenever a review's findings are (re)written, so the stored verdict and
the insights numbers never drift from the findings they summarise.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from app import markets as market_registry
from app.analysis.readiness import build_readiness, is_open, readiness_group
from app.config import get_settings
from app.models import Analysis, AnalysisStat


def markets_of(analysis: Analysis) -> list[str]:
    """Markets applied to a review; older reviews without any use the configured default."""
    try:
        return market_registry.clean(analysis.markets, default=get_settings().default_markets)
    except market_registry.UnknownMarket:
        return list(market_registry.DEFAULT_MARKETS)


def readiness_of(analysis: Analysis) -> dict[str, Any]:
    return build_readiness(
        analysis.findings,
        ai_status=analysis.ai_status,
        analysis_mode=analysis.analysis_mode,
        brief_check=analysis.brief_check,
    )


def refresh(db: Session, analysis: Analysis) -> dict[str, Any]:
    """Store the verdict and upsert the review's stats row. Returns the readiness summary."""
    readiness = readiness_of(analysis)
    analysis.readiness_verdict = readiness["verdict"]
    open_findings = [f for f in analysis.findings if is_open(f)]
    if get_settings().usage_stats_retention_days > 0:
        db.merge(
            AnalysisStat(
                analysis_id=analysis.id,
                created_at=analysis.created_at,
                platform=analysis.platform,
                markets=markets_of(analysis),
                client_label=analysis.client_label,
                analysis_mode=analysis.analysis_mode,
                risk_score=analysis.risk_score,
                risk_level=analysis.risk_level,
                verdict=readiness["verdict"],
                open_findings=len(open_findings),
                severity_counts=dict(Counter(f.severity for f in open_findings)),
                group_counts=dict(Counter(readiness_group(f) for f in open_findings)),
            )
        )
    return readiness
