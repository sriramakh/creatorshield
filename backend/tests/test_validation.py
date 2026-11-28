from __future__ import annotations

from typing import Any

from app.analysis.validation import validate_ai_output
from app.config import get_settings
from app.policies.kb import load_kb
from app.schemas import AIAnalysisOutput, AIEvidence, AIFinding

KB = load_kb(get_settings().policy_kb_path)
EXTRACTION: dict[str, Any] = {
    "transcript": {"segments": [{"id": "T1", "start": 2.0, "end": 5.0, "text": "hello"}]},
    "frames": [
        {"id": "F1", "timestamp": 0.0, "reason": "first", "file": "F1.jpg"},
        {"id": "F2", "timestamp": 8.0, "reason": "uniform", "file": "F2.jpg"},
    ],
    "ocr": [{"id": "O1", "frame_id": "F2", "timestamp": 8.0, "text": "50% OFF"}],
}


def finding(**kw: Any) -> AIFinding:
    base: dict[str, Any] = dict(
        category="spam_deception",
        finding_type="observed_evidence",
        severity="medium",
        confidence="high",
        title="t",
        explanation="e",
        evidence=[],
        start_seconds=None,
        end_seconds=None,
        policy_rule_ids=[],
        suggested_action="a",
        context_exception=None,
        requires_human_review=False,
    )
    base.update(kw)
    return AIFinding(**base)


def run(
    *findings: AIFinding,
    platform: str = "youtube_shorts",
    injected: bool = False,
    is_mock: bool = False,
):  # type: ignore[no-untyped-def]
    out = AIAnalysisOutput(
        summary="s",
        context_assessment="c",
        findings=list(findings),
        unassessable=[],
        embedded_instructions_detected=injected,
    )
    return validate_ai_output(
        out, kb=KB, platform=platform, extraction=EXTRACTION, duration=27.0, is_mock=is_mock
    )


def test_invented_citation_is_removed_and_flagged_for_review() -> None:
    (f,), notes = run(
        finding(
            policy_rule_ids=["YT-MADE-UP-99"],
            evidence=[AIEvidence(source="transcript", ref_id="T1", detail="x")],
        )
    )
    assert f.policy_rule_ids == []
    assert f.requires_human_review is True
    assert any("unverified citation" in n for n in f.validation_notes)
    assert any("citation" in n for n in notes)


def test_citation_for_other_platform_is_removed() -> None:
    (f,), _ = run(finding(policy_rule_ids=["META-CS-SPAM", "YT-CG-SPAM"]))
    assert f.policy_rule_ids == ["YT-CG-SPAM"]


def test_citations_are_normalised_and_deduplicated() -> None:
    (f,), _ = run(finding(policy_rule_ids=[" yt-cg-spam ", "YT-CG-SPAM"]))
    assert f.policy_rule_ids == ["YT-CG-SPAM"]


def test_unknown_evidence_dropped_and_observed_downgraded() -> None:
    (f,), _ = run(
        finding(
            evidence=[AIEvidence(source="frame", ref_id="F99", detail="x")],
            policy_rule_ids=["YT-CG-SPAM"],
        )
    )
    assert f.evidence == []
    assert f.finding_type == "suspected_violation"


def test_timestamps_clamped_to_duration() -> None:
    (f,), _ = run(finding(start_seconds=-4, end_seconds=999, policy_rule_ids=["YT-CG-SPAM"]))
    assert f.start_seconds == 0.0 and f.end_seconds == 27.0


def test_timestamps_derived_from_evidence() -> None:
    (f,), _ = run(
        finding(
            evidence=[
                AIEvidence(source="transcript", ref_id="T1", detail="x"),
                AIEvidence(source="ocr", ref_id="O1", detail="y"),
            ],
            policy_rule_ids=["YT-CG-SPAM"],
        )
    )
    assert (f.start_seconds, f.end_seconds) == (2.0, 8.0)
    assert [e["timestamp"] for e in f.evidence] == [2.0, 8.0]


def test_embedded_instruction_flag_produces_note() -> None:
    _, notes = run(injected=True)
    assert any("addressed to an AI reviewer" in n for n in notes)


def test_mock_findings_are_labelled() -> None:
    (f,), _ = run(finding(title="Something"), is_mock=True)
    assert f.title.startswith("[MOCK]")


# --- Regressions from the analysis-engine review -------------------------------

THUMBNAIL_EXTRACTION: dict[str, Any] = {
    "transcript": {"segments": []},
    "frames": [{"id": "F1", "timestamp": 0.0, "reason": "thumbnail", "file": "F1.jpg"}],
    "ocr": [{"id": "O1", "frame_id": "F1", "timestamp": 0.0, "text": "MIRACLE CURE"}],
}


def _run_on(extraction: dict[str, Any], duration: float | None, *findings: AIFinding):  # type: ignore[no-untyped-def]
    out = AIAnalysisOutput(
        summary="s",
        context_assessment="c",
        findings=list(findings),
        unassessable=[],
        embedded_instructions_detected=False,
    )
    return validate_ai_output(
        out, kb=KB, platform="instagram_reels", extraction=extraction, duration=duration
    )


def test_thumbnail_only_review_has_no_fake_timestamps() -> None:
    f = finding(
        evidence=[
            AIEvidence(source="ocr", ref_id="O1", detail="cover text"),
            AIEvidence(source="frame", ref_id="F1", detail="cover"),
        ],
        start_seconds=0.0,
        end_seconds=3.0,
    )
    (v,), _ = _run_on(THUMBNAIL_EXTRACTION, None, f)
    assert v.start_seconds is None and v.end_seconds is None
    assert all(e["timestamp"] is None for e in v.evidence)


def test_thumbnail_ocr_has_no_timestamp_even_when_duration_is_known() -> None:
    f = finding(evidence=[AIEvidence(source="ocr", ref_id="O1", detail="cover text")])
    (v,), _ = _run_on(THUMBNAIL_EXTRACTION, 30.0, f)
    assert v.start_seconds is None and v.evidence[0]["timestamp"] is None


def test_end_without_start_is_dropped() -> None:
    (v,), _ = run(finding(start_seconds=None, end_seconds=4.0))
    assert v.start_seconds is None and v.end_seconds is None
