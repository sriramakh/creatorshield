from __future__ import annotations

from typing import Any

from app.analysis.merge import merge_findings
from app.schemas import FindingDraft


def draft(source: str, **kw: Any) -> FindingDraft:
    base: dict[str, Any] = dict(
        source=source,
        category="disclosure",
        finding_type="suspected_violation",
        severity="medium",
        confidence="medium",
        title=f"{source} finding",
        explanation="e",
        suggested_action="a",
        requires_human_review=False,
    )
    base.update(kw)
    return FindingDraft(**base)


def ev(*refs: str) -> list[dict[str, Any]]:
    return [{"source": "transcript", "ref_id": r, "detail": "d", "timestamp": 1.0} for r in refs]


def test_shared_evidence_merges_into_ai_finding() -> None:
    det = draft(
        "deterministic",
        evidence=ev("T5", "T6", "O3"),
        policy_rule_ids=["IN-ASCI-INFLUENCER"],
        requires_human_review=True,
    )
    ai = draft("ai", evidence=ev("T5", "O3"), policy_rule_ids=["YT-DISC-PAID-PROMO"])
    out = merge_findings([det], [ai])
    assert len(out) == 1
    m = out[0]
    assert m.source == "combined"
    assert m.policy_rule_ids == ["YT-DISC-PAID-PROMO", "IN-ASCI-INFLUENCER"]
    assert {e["ref_id"] for e in m.evidence} == {"T5", "T6", "O3"}
    assert m.requires_human_review is True
    assert any("Corroborated" in n for n in m.validation_notes)


def test_same_category_overlapping_time_merges_and_keeps_higher_severity() -> None:
    det = draft(
        "deterministic",
        category="licensing",
        severity="high",
        start_seconds=21.0,
        end_seconds=27.0,
        evidence=ev("A1"),
    )
    ai = draft("ai", category="licensing", severity="medium", start_seconds=21.5, end_seconds=26.0)
    (m,) = merge_findings([det], [ai])
    assert m.severity == "high" and m.source == "combined"


def test_unrelated_findings_and_cannot_check_are_kept() -> None:
    det = draft(
        "deterministic",
        category="originality",
        start_seconds=2.0,
        end_seconds=3.0,
        evidence=ev("O1"),
    )
    cc = draft("deterministic", finding_type="cannot_check", severity="info")
    ai = draft("ai", category="disclosure", start_seconds=10.0, end_seconds=12.0, evidence=ev("T4"))
    out = merge_findings([det, cc], [ai])
    assert [f.source for f in out] == ["ai", "deterministic", "deterministic"]


def test_no_ai_findings_returns_deterministic_unchanged() -> None:
    det = draft("deterministic", evidence=ev("T1"))
    assert merge_findings([det], []) == [det]


def test_single_shared_ref_does_not_merge_across_categories() -> None:
    """Regression: live run folded a disclosure finding into a health-claim finding."""
    disclosure = draft(
        "deterministic",
        category="disclosure",
        evidence=ev("T5", "T6", "O3"),
        start_seconds=13.9,
        end_seconds=20.1,
    )
    health_det = draft(
        "deterministic",
        category="spam_deception",
        evidence=ev("T3", "T4", "T5", "O2"),
        start_seconds=7.0,
        end_seconds=18.9,
    )
    medical_ai = draft(
        "ai",
        category="harmful_content",
        evidence=ev("T3", "O2", "T4", "T5"),
        start_seconds=7.3,
        end_seconds=13.9,
        policy_rule_ids=["YT-CG-MEDMISINFO"],
    )
    disclosure_ai = draft(
        "ai",
        category="disclosure",
        evidence=ev("T5", "O3", "T6"),
        start_seconds=13.9,
        end_seconds=20.1,
        policy_rule_ids=["YT-DISC-PAID-PROMO"],
    )
    out = merge_findings([disclosure, health_det], [medical_ai, disclosure_ai])
    medical = next(f for f in out if "YT-CG-MEDMISINFO" in f.policy_rule_ids)
    assert "YT-DISC-PAID-PROMO" not in medical.policy_rule_ids
    assert medical.source == "combined"  # corroborated by the health-claim rule (4/4 refs)
    disc = next(f for f in out if f.category == "disclosure")
    assert disc.source == "combined" and len(out) == 2
