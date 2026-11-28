"""Brand-brief checks: required lines, restricted wording, hashtags, handles."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.analysis.brief import MAX_ITEMS, BriefSpec, run_brief_checks

EXTRACTION = {
    "transcript": {
        "segments": [
            {"id": "T1", "start": 0.0, "end": 3.0, "text": "Hi everyone, this is my morning"},
            {
                "id": "T2",
                "start": 3.0,
                "end": 6.5,
                "text": "routine with the GlowUp vitamin C serum.",
            },
            {"id": "T3", "start": 6.5, "end": 9.0, "text": "It is way better than Lumina."},
        ]
    },
    "ocr": [{"id": "O1", "timestamp": 4.0, "text": "Dermatologist tested"}],
}


def _items(summary: dict, kind: str) -> dict[str, str]:
    return {i["text"]: i["status"] for i in summary["items"] if i["kind"] == kind}


def test_required_lines_match_across_punctuation_case_and_segments() -> None:
    brief = BriefSpec(
        brand="GlowUp",
        must_say=["vitamin c serum", "DERMATOLOGIST-TESTED", "morning routine", "patch test first"],
    )
    summary, findings = run_brief_checks(brief, "My routine", [], EXTRACTION)
    statuses = _items(summary, "must_say")
    assert statuses["vitamin c serum"] == "met"
    assert statuses["DERMATOLOGIST-TESTED"] == "met"  # found in on-screen text
    assert statuses["morning routine"] == "met"  # spans T1 and T2
    assert statuses["patch test first"] == "missing"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.category == "brand_brief"
    assert finding.severity == "medium"
    assert '"patch test first"' in finding.explanation
    assert finding.requires_human_review is True
    assert finding.policy_rule_ids == []


def test_restricted_wording_and_competitors_are_high_with_timestamps() -> None:
    brief = BriefSpec(brand="GlowUp", must_not_say=["cures acne"], competitors=["Lumina"])
    summary, findings = run_brief_checks(
        brief, "This cures acne overnight", ["skincare"], EXTRACTION
    )
    assert _items(summary, "must_not_say") == {"cures acne": "violated"}
    assert _items(summary, "competitor") == {"Lumina": "violated"}
    by_title = {f.title: f for f in findings}
    restricted = next(f for t, f in by_title.items() if "restricted wording" in t)
    competitor = next(f for t, f in by_title.items() if "competitor" in t)
    assert restricted.severity == competitor.severity == "high"
    # Caption-only evidence is certain; speech evidence asks for a human look.
    assert restricted.confidence == "high" and restricted.requires_human_review is False
    assert competitor.confidence == "medium" and competitor.requires_human_review is True
    assert competitor.start_seconds == 6.5
    assert competitor.evidence[0]["ref_id"] == "T3"


def test_restricted_word_does_not_match_inside_another_word() -> None:
    brief = BriefSpec(must_not_say=["cure"], competitors=["Lumina"])
    summary, findings = run_brief_checks(brief, "A secure, illuminating look", [], {})
    assert findings == []
    assert summary["failed"] == 0


def test_hashtags_and_mentions_come_from_caption_or_hashtag_field() -> None:
    brief = BriefSpec(
        brand="GlowUp",
        required_hashtags=["#GlowUpPartner", "ad", "skincare"],
        required_mentions=["@glowup.official", "glow"],
    )
    summary, findings = run_brief_checks(
        brief, "Loving this #glowuppartner @GlowUp.Official", ["Skincare"], {}
    )
    assert _items(summary, "required_hashtag") == {
        "#GlowUpPartner": "met",
        "#ad": "missing",
        "#skincare": "met",
    }
    # "@glow" must not be satisfied by "@glowup.official".
    assert _items(summary, "required_mention") == {"@glowup.official": "met", "@glow": "missing"}
    titles = [f.title for f in findings]
    assert "Brand brief: required hashtags are missing" in titles
    assert "Brand brief: required account mentions are missing" in titles
    assert all(f.requires_human_review is False for f in findings)


@pytest.mark.parametrize(
    ("caption", "status"),
    [
        ("#ad Loving my new serum", "met"),
        ("Loving my new serum " + "x" * 90 + " #ad", "missing"),
        ("Loving my new serum", "missing"),
        ("#advantage is mine", "missing"),
    ],
)
def test_required_disclosure_must_open_the_caption(caption: str, status: str) -> None:
    summary, findings = run_brief_checks(BriefSpec(required_disclosure="#ad"), caption, [], {})
    assert _items(summary, "required_disclosure") == {"#ad": status}
    assert bool(findings) is (status == "missing")


def test_caption_only_scope_leaves_video_requirements_unverified() -> None:
    brief = BriefSpec(must_say=["patch test first"], must_not_say=["miracle"])
    summary, findings = run_brief_checks(brief, "My routine", [], {}, analysis_mode="metadata_only")
    assert summary["scope"] == "caption_only"
    assert _items(summary, "must_say") == {"patch test first": "unverified"}
    assert _items(summary, "must_not_say") == {"miracle": "unverified"}
    assert findings == []
    assert summary["unverified"] == 2 and summary["failed"] == 0


def test_everything_met_gives_no_findings() -> None:
    brief = BriefSpec(
        brand="GlowUp",
        must_say=["vitamin C serum"],
        required_hashtags=["ad"],
        required_disclosure="Ad:",
    )
    summary, findings = run_brief_checks(brief, "Ad: my routine #ad", [], EXTRACTION)
    assert findings == []
    assert summary["met"] == summary["total"] == 3


def test_brief_input_is_cleaned_and_bounded() -> None:
    brief = BriefSpec(
        must_say=["  Patch   test ", "patch test", ""],
        required_hashtags=["#Ad", "ad"],
        required_mentions=["@Brand"],
        required_disclosure="   ",
    )
    assert brief.must_say == ["Patch test"]
    assert brief.required_hashtags == ["Ad"]
    assert brief.required_mentions == ["Brand"]
    assert brief.required_disclosure is None
    assert BriefSpec().is_empty()
    with pytest.raises(ValidationError):
        BriefSpec(must_say=[f"line {i}" for i in range(MAX_ITEMS + 1)])
    with pytest.raises(ValidationError):
        BriefSpec(must_say=["x" * 201])
