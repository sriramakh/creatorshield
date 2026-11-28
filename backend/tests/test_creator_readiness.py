"""Publish-readiness verdict and checklist."""

from __future__ import annotations

from typing import Any

from app.analysis.readiness import build_readiness


def _f(category: str, severity: str, **kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": f"{category}-{severity}",
        "category": category,
        "severity": severity,
        "confidence": "medium",
        "finding_type": "suspected_violation",
        "source": "deterministic",
        "policy_rule_ids": [],
        "requires_human_review": False,
        "rights_status": None,
    }
    base.update(kw)
    return base


def _row(result: dict[str, Any], key: str) -> dict[str, Any]:
    return next(c for c in result["checklist"] if c["key"] == key)


def test_clean_review_with_ai_is_ready_and_never_says_safe() -> None:
    result = build_readiness([], ai_status="completed")
    assert result["verdict"] == "ready"
    assert result["headline"] == "No issues found by these checks"
    assert result["blockers"] == 0 and result["warnings"] == 0
    assert {c["status"] for c in result["checklist"]} == {"pass"}
    text = str(result).lower()
    assert all(word not in text for word in ("safe", "approved", "compliant", "cleared"))


def test_without_ai_the_best_verdict_is_review() -> None:
    for status in ("skipped", "failed", "mock", None):
        result = build_readiness([], ai_status=status)
        assert result["verdict"] == "review"
        assert _row(result, "ai_review")["status"] == "warn"


def test_missing_disclosure_blocks() -> None:
    finding = _f("disclosure", "medium")
    result = build_readiness([finding], ai_status="completed")
    assert result["verdict"] == "fix_first"
    assert result["headline"] == "Fix before posting"
    row = _row(result, "disclosure")
    assert row["status"] == "fail"
    assert row["finding_ids"] == ["disclosure-medium"]
    assert result["blockers"] == 1


def test_disclosure_wording_found_still_asks_for_a_look() -> None:
    note = _f(
        "disclosure", "info", finding_type="cannot_check", requires_human_review=True, id="note"
    )
    result = build_readiness([note], ai_status="completed")
    assert _row(result, "disclosure")["status"] == "warn"
    assert result["verdict"] == "review"


def test_community_medium_warns_and_high_blocks() -> None:
    medium = build_readiness([_f("community_guidelines", "medium")], ai_status="completed")
    assert _row(medium, "community")["status"] == "warn"
    assert medium["verdict"] == "review"
    high = build_readiness([_f("harmful_content", "high")], ai_status="completed")
    assert _row(high, "community")["status"] == "fail"
    assert high["verdict"] == "fix_first"


def test_low_confidence_high_severity_does_not_block_alone() -> None:
    result = build_readiness(
        [_f("community_guidelines", "critical", confidence="low")], ai_status="completed"
    )
    assert _row(result, "community")["status"] == "warn"
    assert result["verdict"] == "review"


def test_rule_ids_route_findings_to_the_community_row() -> None:
    hashtags = _f("spam_deception", "medium", policy_rule_ids=["YT-HASHTAGS"])
    claims = _f("spam_deception", "medium", policy_rule_ids=["IG-MON-CONTENT"], id="claims")
    result = build_readiness([hashtags, claims], ai_status="completed")
    assert _row(result, "community")["finding_ids"] == ["spam_deception-medium"]
    assert _row(result, "claims")["finding_ids"] == ["claims"]
    assert _row(result, "claims")["status"] == "fail"


def test_covered_duplicate_and_cannot_check_items_do_not_count() -> None:
    findings = [
        _f("licensing", "high", rights_status="covered"),
        _f("originality", "high", rights_status="duplicate", id="dup"),
        _f("licensing", "info", finding_type="cannot_check", id="cc"),
    ]
    result = build_readiness(findings, ai_status="completed")
    assert _row(result, "rights")["status"] == "pass"
    assert result["verdict"] == "ready"


def test_provenance_findings_land_in_rights() -> None:
    finding = _f("disclosure", "high", source="provenance")
    result = build_readiness([finding], ai_status="completed")
    assert _row(result, "rights")["status"] == "fail"
    assert _row(result, "disclosure")["status"] == "pass"


def test_brief_row_only_appears_with_a_brief() -> None:
    assert all(c["key"] != "brief" for c in build_readiness([], ai_status="completed")["checklist"])
    met = build_readiness(
        [], ai_status="completed", brief_check={"total": 3, "met": 3, "unverified": 0}
    )
    assert _row(met, "brief") == {
        "key": "brief",
        "label": "Brand brief",
        "status": "pass",
        "detail": "3 of 3 requirements met",
        "finding_ids": [],
    }
    failed = build_readiness(
        [_f("brand_brief", "high")],
        ai_status="completed",
        brief_check={"total": 3, "met": 2, "unverified": 0},
    )
    assert _row(failed, "brief")["status"] == "fail"
    assert _row(failed, "brief")["detail"] == "2 of 3 requirements met"
    assert failed["verdict"] == "fix_first"
    unverified = build_readiness(
        [], ai_status="completed", brief_check={"total": 2, "met": 1, "unverified": 1}
    )
    assert _row(unverified, "brief")["status"] == "warn"


def test_limited_modes_warn_about_coverage() -> None:
    result = build_readiness([], ai_status="completed", analysis_mode="metadata_only")
    assert _row(result, "coverage")["status"] == "warn"
    assert result["verdict"] == "review"


def test_caption_only_check_has_no_rights_or_ai_rows() -> None:
    result = build_readiness([], ai_status=None, caption_only=True)
    keys = [c["key"] for c in result["checklist"]]
    assert keys == ["disclosure", "community", "claims", "coverage"]
    assert _row(result, "coverage")["status"] == "unknown"
    # Nothing to fix in the text itself: a caption check can be "ready".
    assert result["verdict"] == "ready"


def test_human_review_finding_keeps_verdict_at_review() -> None:
    finding = _f("community_guidelines", "low", requires_human_review=True)
    result = build_readiness([finding], ai_status="completed")
    assert result["verdict"] == "review"
