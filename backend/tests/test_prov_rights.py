"""Regression tests for rights coverage: record types, status, client scoping, term
matching, reconcile duplicates and the evidence-pack draft. Pure: no services needed."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any

from app.provenance.evidence_pack import dispute_draft, redact_lines, relied_lines
from app.provenance.findings import build
from app.provenance.ledger import LedgerEntry, domain_matches, name_matches
from app.provenance.reconcile import reconcile
from app.schemas import FindingDraft

TODAY = date(2026, 11, 28)


def entry(
    kind: str,
    name: str,
    *terms: str,
    until: date | None = None,
    starts: date | None = None,
    client: str | None = None,
) -> LedgerEntry:
    return LedgerEntry(
        id=str(uuid.uuid4()),
        kind=kind,
        counterparty=name,
        terms=list(terms) or [name],
        platforms=[],
        client_label=client,
        valid_from=starts,
        valid_until=until,
        reference="REF-1",
        has_proof=False,
    )


def review(
    prov: dict[str, Any],
    records: list[LedgerEntry] | None = None,
    *,
    caption: str = "",
    connected: set[str] | None = None,
    connected_review: set[str] | None = None,
    extraction: dict[str, Any] | None = None,
) -> tuple[list[FindingDraft], list[dict[str, Any]]]:
    return build(
        provenance=prov,
        platform="instagram_reels",
        client_label="Client B",
        caption=caption,
        hashtags=[],
        extraction=extraction or {"transcript": {"segments": []}, "ocr": []},
        entries=records or [],
        connected=connected or set(),
        connected_review=connected_review,
        today=TODAY,
    )


NIKE = {
    "cues": {
        "handles": [{"handle": "@nike", "ref_id": "O1", "timestamp": 1.0, "text": "via @nike"}],
        "broadcasters": [],
    }
}
OCR = {"transcript": {"segments": []}, "ocr": [{"id": "O1", "frame_id": "F1", "text": "via @nike"}]}


# --------------------------------------------------------------------------- 2: brand agreements


def test_expired_brand_agreement_does_not_clear_an_on_screen_handle() -> None:
    ended = entry("brand_agreement", "Nike", "@nike", "Nike", until=TODAY - timedelta(days=300))
    findings, lines = review(NIKE, [ended], caption="Ad: paid partnership with Nike")
    handle = next(line for line in lines if line["area"] == "handle")
    assert handle["status"] == "missing"
    assert any(f.title.startswith("Another account's handle") for f in findings)


def test_active_brand_agreement_is_info_never_footage_coverage() -> None:
    active = entry("brand_agreement", "Nike", "@nike", "Nike")
    findings, lines = review(NIKE, [active], caption="Ad: paid partnership with Nike")
    handle = next(line for line in lines if line["area"] == "handle")
    assert handle["status"] == "info" and "not permission" in handle["detail"]
    assert not any(f.title.startswith("Another account's handle") for f in findings)


def test_handle_is_covered_only_by_permission_type_records() -> None:
    for kind in ("music_license", "brand_agreement"):
        stale = entry(kind, "Nike", "@nike", until=TODAY - timedelta(days=1))
        _, lines = review(NIKE, [stale])
        assert lines[0]["status"] != "covered"
    _, lines = review(NIKE, [entry("footage_license", "Nike", "@nike")])
    assert lines[0]["status"] == "covered"


# --------------------------------------------------------------------------- 3: connected accounts


def test_connected_account_of_another_client_is_review_not_own() -> None:
    findings, lines = review(NIKE, connected_review={"nike"})
    assert lines[0]["status"] == "review" and findings == []
    _, lines = review(NIKE, connected={"nike"})
    assert lines[0]["status"] == "own"


# --------------------------------------------------------------------------- 8: term matching


def test_name_and_domain_matching_rules() -> None:
    assert name_matches("Sony Music", "sony  music")
    assert name_matches("T-Series", "T Series")
    assert not name_matches("Sony", "Sony Music")
    assert not name_matches("@sony", "Sony")
    assert domain_matches("studio.example", "www.studio.example")
    assert domain_matches("https://studio.example/about", "cdn.studio.example")
    assert not domain_matches("studio.example", "studio.example.evil.io")
    assert not domain_matches("My Channel", "mychannel.example")


def test_broad_licence_term_does_not_cover_a_longer_brand_name() -> None:
    prov = {
        "cues": {
            "broadcasters": [{"name": "Sony Music", "ref_id": "O1", "timestamp": 1, "text": "x"}]
        }
    }
    findings, lines = review(prov, [entry("footage_license", "Sony Pictures", "Sony")])
    assert findings and lines[0]["status"] == "missing"
    findings, lines = review(prov, [entry("footage_license", "Sony Music", "Sony Music")])
    assert findings == [] and lines[0]["status"] == "covered"


def test_music_licence_must_name_the_label_artist_or_track() -> None:
    clip = {"matched": True, "title": "Song", "artist": "Artist", "label": "Sony Music"}
    prov = {"music": {"is_mock": False, "clips": [clip]}}
    _, lines = review(prov, [entry("music_license", "Sony", "Sony")])
    assert lines[0]["status"] == "missing"
    _, lines = review(prov, [entry("music_license", "Sony Music", "Sony Music")])
    assert lines[0]["status"] == "covered"


def _web(title: str, domain: str) -> dict[str, Any]:
    page = {"url": f"https://{domain}/p", "title": title, "domain": domain, "full_match": True}
    return {"web": {"frames": [{"frame_id": "F1", "timestamp": 1, "pages": [page]}]}}


def test_third_party_page_title_cannot_be_covered_by_an_own_channel_term() -> None:
    own = entry("own_channel", "Client B", "Client B", "clientb.example")
    findings, lines = review(_web("Client B video leaked", "pirate.example"), [own])
    assert findings and lines[0]["status"] == "missing"
    findings, lines = review(_web("Anything", "www.clientb.example"), [own])
    assert findings == [] and lines[0]["status"] == "covered"


# --------------------------------------------------------------------------- 9: reconcile


def _ai(category: str, title: str, refs: list[str], severity: str = "medium") -> FindingDraft:
    return FindingDraft(
        source="ai",
        category=category,  # type: ignore[arg-type]
        finding_type="licensing_uncertainty",
        severity=severity,  # type: ignore[arg-type]
        confidence="medium",
        title=title,
        explanation="",
        suggested_action="x",
        evidence=[{"source": "frame", "ref_id": r, "detail": "", "timestamp": 0.0} for r in refs],
    )


def test_shared_frame_alone_does_not_make_a_different_issue_a_duplicate() -> None:
    found, lines = review(NIKE, extraction=OCR)
    film = _ai("licensing", "Film footage from a studio release", ["F1"])
    reconcile([*found, film], lines, NIKE, OCR)
    assert film.rights_status is None  # still counted
    assert all(f.rights_status is None for f in found)

    found, lines = review(NIKE, extraction=OCR)
    same = _ai("originality", "Reposted clip", ["F1"])
    reconcile([*found, same], lines, NIKE, OCR)
    assert same.rights_status == "duplicate"  # same frame and same kind of issue

    found, lines = review(NIKE, extraction=OCR)
    named = _ai("licensing", "Clip credited to @nike", [])
    reconcile([*found, named], lines, NIKE, OCR)
    assert named.rights_status == "duplicate"  # names the same subject


# --------------------------------------------------------------------------- 1/5: dispute draft


def _analysis() -> Any:
    return SimpleNamespace(
        id=uuid.uuid4(),
        source_title="My video",
        caption="",
        created_at=None,
        provenance={"fingerprint": {"sha256": "ab" * 32}, "catalogue": {}},
        client_label="Client B",
    )


def _covered_line(record_id: str, status: str = "active") -> dict[str, Any]:
    return {
        "area": "handle",
        "subject": "@clipsdaily",
        "status": "covered",
        "detail": "Permission recorded.",
        "records": [
            {
                "record_id": record_id,
                "kind_label": "Permission from a creator",
                "counterparty": "Clips Daily",
                "reference": "Email 1",
                "status": status,
            }
        ],
        "start_seconds": 1.0,
        "end_seconds": None,
    }


def test_dispute_draft_never_states_coverage_from_expired_or_deleted_records() -> None:
    rid = str(uuid.uuid4())
    line = _covered_line(rid)
    active = SimpleNamespace(valid_from=None, valid_until=None)
    ended = SimpleNamespace(valid_from=None, valid_until=TODAY - timedelta(days=1))

    ok = dispute_draft(_analysis(), [line], records={rid: active}, today=TODAY)  # type: ignore[dict-item]
    assert "is used under Permission from a creator with Clips Daily" in ok

    for records in ({rid: ended}, {rid: None}):
        text = dispute_draft(_analysis(), [line], records=records, today=TODAY)  # type: ignore[arg-type]
        assert "is used under" not in text
        assert "No active rights-ledger entries" in text
        assert "has ended or was deleted" in text

    # Without ledger rows, a line whose stored record status is not active is not relied on.
    stale = dispute_draft(_analysis(), [_covered_line(rid, status="expired")], today=TODAY)
    assert "is used under" not in stale


def test_only_covered_and_own_lines_are_relied_on() -> None:
    rid = str(uuid.uuid4())
    info = {**_covered_line(rid), "status": "info"}
    missing = {**_covered_line(rid), "status": "missing", "records": []}
    relied, gaps = relied_lines([info, missing], {rid: None}, TODAY)
    assert relied == [] and gaps == [missing]


def test_redact_lines_hides_other_clients() -> None:
    analysis = _analysis()
    analysis.provenance["catalogue"] = {
        "owner_label": "Client B",
        "matches": [
            {"owner_label": "Client C", "title": "C's secret launch", "same_owner": False},
            {"owner_label": "Client B", "title": "My old post", "same_owner": True},
        ],
    }
    lines = [
        {
            "area": "catalogue",
            "subject": "Client C: C's secret launch",
            "status": "missing",
            "detail": "0:00-0:12 shows the same footage under a different client.",
            "records": [],
            "match": {"analysis_id": "x", "fingerprint_id": "y"},
        },
        {"area": "catalogue", "subject": "Client B: My old post", "status": "own", "detail": ""},
    ]
    out = redact_lines(analysis, lines)
    text = str(out)
    assert "Client C" not in text and "secret launch" not in text
    assert "another client in this workspace" in out[0]["subject"]
    assert out[0]["match"]["analysis_id"] is None
    assert out[1]["subject"] == "Client B: My old post"
