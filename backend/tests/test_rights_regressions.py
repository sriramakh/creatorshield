"""Regression cases for unsafe rights coverage; pure tests require no services."""

from datetime import date

import pytest

from app.analysis.risk import compute_risk
from app.provenance.findings import build
from app.provenance.ledger import LedgerEntry
from app.provenance.reconcile import reconcile
from app.schemas import FindingDraft

TODAY = date(2026, 11, 9)


def entry(kind="footage_license", state="active", term="Studio"):
    return LedgerEntry(
        "record",
        kind,
        term,
        [term],
        [],
        "Client A",
        date(2027, 1, 1) if state == "future" else None,
        date(2020, 1, 1) if state == "expired" else None,
        "proof",
        True,
    )


def review(prov, records):
    return build(
        provenance=prov,
        platform="youtube_shorts",
        client_label="Client A",
        caption="",
        hashtags=[],
        extraction={},
        entries=records,
        connected=set(),
        today=TODAY,
    )


BROADCAST = {
    "cues": {"broadcasters": [{"name": "Studio", "ref_id": "O1", "text": "Studio", "timestamp": 1}]}
}
WEB = {
    "web": {
        "frames": [
            {
                "frame_id": "F1",
                "timestamp": 1,
                "pages": [
                    {
                        "domain": "Studio",
                        "title": "Film",
                        "url": "https://studio.example/film",
                        "full_match": True,
                    }
                ],
            }
        ]
    }
}


@pytest.mark.parametrize("prov", [BROADCAST, WEB])
@pytest.mark.parametrize("kind", ["music_license", "brand_agreement"])
def test_wrong_licence_type_cannot_cover_footage(prov, kind):
    findings, lines = review(prov, [entry(kind)])
    assert findings
    assert lines[0]["status"] != "covered"


@pytest.mark.parametrize("prov", [BROADCAST, WEB])
@pytest.mark.parametrize("state", ["expired", "future"])
def test_inactive_record_cannot_cover_footage(prov, state):
    findings, lines = review(prov, [entry(state=state)])
    assert findings
    assert lines[0]["status"] != "covered"


@pytest.mark.parametrize("state", ["expired", "future"])
def test_inactive_own_channel_does_not_clear_handle(state):
    findings, lines = review(
        {
            "cues": {
                "handles": [
                    {"handle": "@studio", "ref_id": "O1", "text": "@studio", "timestamp": 1}
                ]
            }
        },
        [entry("own_channel", state, "@studio")],
    )
    assert findings
    assert lines[0]["status"] in {"expired", "not_started"}


@pytest.mark.parametrize("prov", [BROADCAST, WEB])
def test_active_footage_licence_still_covers_specific_provenance(prov):
    findings, lines = review(prov, [entry()])
    assert findings == []
    assert lines[0]["status"] == "covered"


@pytest.mark.parametrize(
    "explanation", ["Unrelated movie rights", "Studio broadcast and unrelated movie rights"]
)
def test_shared_frame_or_name_does_not_clear_entire_ai_finding(explanation):
    finding = FindingDraft(
        source="ai",
        category="licensing",
        finding_type="licensing_uncertainty",
        severity="high",
        confidence="high",
        title="Check rights",
        explanation=explanation,
        suggested_action="Verify both",
        evidence=[{"ref_id": "F1"}],
        rights_status="covered",
    )
    expected = compute_risk([finding.model_copy(update={"rights_status": None})])
    _, lines = review(BROADCAST, [entry()])
    reconcile([finding], lines, BROADCAST, {"ocr": [{"id": "O1", "frame_id": "F1"}]})
    assert finding.rights_status is None
    assert finding.requires_human_review
    assert compute_risk([finding]) == expected
    assert "still counts" in finding.rights_note


def test_one_covered_web_match_does_not_clear_other_partial_match():
    import copy

    prov = copy.deepcopy(WEB)
    prov["web"]["frames"][0]["pages"].append(
        {
            "domain": "Other",
            "title": "Other film",
            "url": "https://other.example",
            "full_match": False,
        }
    )
    findings, lines = review(prov, [entry()])
    assert findings and lines[0]["status"] == "missing"
