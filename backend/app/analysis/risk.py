"""Heuristic overall risk indicator.

This is NOT a probability of removal, strikes or suspension. It summarises the
number, severity, type and confidence of findings so creators can prioritise.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

SEVERITY_WEIGHT = {"critical": 40, "high": 22, "medium": 10, "low": 4, "info": 0}
TYPE_WEIGHT = {
    "observed_evidence": 1.0,
    "suspected_violation": 0.7,
    "licensing_uncertainty": 0.5,
    "cannot_check": 0.0,
}
CONFIDENCE_WEIGHT = {"high": 1.0, "medium": 0.75, "low": 0.45}


class _FindingLike(Protocol):
    @property
    def severity(self) -> str: ...
    @property
    def finding_type(self) -> str: ...
    @property
    def confidence(self) -> str: ...


def compute_risk(findings: Iterable[_FindingLike]) -> tuple[int, str]:
    """Return (score 0-100, level in low|moderate|elevated|high)."""
    # Findings the rights ledger covers, or that duplicate a provenance finding,
    # are shown but not counted. Brand-brief findings are contract checks, not
    # policy risk: they feed the readiness checklist instead.
    items = [
        f
        for f in findings
        if getattr(f, "rights_status", None) is None
        and getattr(f, "category", None) != "brand_brief"
    ]
    raw = sum(
        SEVERITY_WEIGHT.get(f.severity, 0)
        * TYPE_WEIGHT.get(f.finding_type, 0)
        * CONFIDENCE_WEIGHT.get(f.confidence, 0.5)
        for f in items
    )
    score = min(100, round(raw))
    counted = [f for f in items if f.finding_type != "cannot_check"]
    # Confidence is treated the same way for both levels: a low-confidence
    # finding moves the overall level one step less than a confident one.
    confident = [f for f in counted if f.confidence != "low"]
    has_critical = any(f.severity == "critical" for f in confident)
    has_high = any(f.severity in ("critical", "high") for f in confident) or any(
        f.severity == "critical" for f in counted
    )
    if has_critical or score >= 60:
        level = "high"
    elif has_high or score >= 30:
        level = "elevated"
    elif score >= 8:
        level = "moderate"
    else:
        level = "low"
    return score, level
