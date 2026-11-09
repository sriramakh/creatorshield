from datetime import date

import pytest
from pydantic import ValidationError

from app.analysis.deterministic import run_deterministic_checks
from app.analysis.disclosure import caption_disclosure
from app.provenance.findings import build
from app.provenance.ledger import LedgerEntry
from app.schemas import SponsorshipInput


@pytest.mark.parametrize(
    "text",
    [
        "Not sponsored",
        "This is not an ad",
        "No paid partnership",
        "Never sponsored",
        "Maybe sponsored",
        "If sponsored",
        "प्रायोजित नहीं",
        "Use my code. " + "x" * 100 + " #ad",
        "#one #two #three #ad",
        "Read more\n#ad",
    ],
)
def test_denied_uncertain_or_buried_label_is_not_opening_disclosure(text):
    assert not caption_disclosure(text)


@pytest.mark.parametrize(
    "label",
    [
        "#ad",
        "Advertisement",
        "Sponsored",
        "Collaboration",
        "Partnership",
        "Employee",
        "Free gift",
        "Affiliate",
        "Paid partnership",
        "विज्ञापन",
        "प्रायोजित",
    ],
)
def test_accepted_wording_is_detected_without_clearance(label):
    findings = run_deterministic_checks(
        "instagram_reels",
        label + " Brand",
        [],
        {},
        30,
        sponsorship={"relationship": "paid", "sponsors": ["Brand"]},
    )
    assert not [
        f for f in findings if f.category == "disclosure" and f.finding_type != "cannot_check"
    ]
    review = next(f for f in findings if f.title == "Disclosure adequacy needs human review")
    assert review.requires_human_review
    assert "duration" in review.explanation
    assert "not verified" in review.suggested_action


def test_declared_paid_relationship_requires_review_without_promo_keywords():
    findings = run_deterministic_checks(
        "youtube_shorts",
        "My morning",
        [],
        {},
        30,
        sponsorship={"relationship": "paid", "sponsors": ["Brand"]},
    )
    assert any(
        f.category == "disclosure" and f.finding_type == "suspected_violation" for f in findings
    )


def test_separate_hashtags_and_late_video_label_do_not_establish_caption_adequacy():
    findings = run_deterministic_checks(
        "youtube_shorts",
        "Use code SAVE20",
        ["ad"],
        {"ocr": [{"id": "O1", "frame_id": "F1", "timestamp": 29, "text": "#ad"}]},
        30,
    )
    assert any(
        f.category == "disclosure" and f.finding_type == "suspected_violation" for f in findings
    )


def test_each_recorded_sponsor_needs_associated_wording():
    entries = [
        LedgerEntry(n, "brand_agreement", n, [n], [], None, None, None, "", False)
        for n in ["Alpha", "Beta"]
    ]
    findings, lines = build(
        provenance={},
        platform="youtube_shorts",
        client_label=None,
        caption="Sponsored by Alpha. Also try Beta.",
        hashtags=[],
        extraction={},
        entries=entries,
        connected=set(),
        today=date(2026, 11, 9),
    )
    assert any("Beta" in f.title for f in findings)
    assert not any("Alpha" in f.title for f in findings)
    assert next(line for line in lines if line["subject"] == "Alpha")["status"] == "info"
    assert not caption_disclosure("Sponsored by Alpha. Also try Beta.", ["Alpha", "Beta"])
    assert caption_disclosure("Sponsored by Alpha and Beta.", ["Alpha", "Beta"])


def test_sponsorship_input_bounds():
    with pytest.raises(ValidationError):
        SponsorshipInput(sponsors=["x"] * 11)
    with pytest.raises(ValidationError):
        SponsorshipInput(relationship="invalid")
    with pytest.raises(ValidationError):
        SponsorshipInput(sponsors=[" "])
    assert SponsorshipInput(sponsors=[" Brand ", "Brand"]).sponsors == ["Brand"]


def test_sponsorship_survives_database_roundtrip():
    from datetime import UTC, datetime

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.db import Base
    from app.models import Analysis

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        row = Analysis(
            expires_at=datetime.now(UTC),
            platform="youtube_shorts",
            language="en",
            file_ext=".mp4",
            content_type="video/mp4",
            size_bytes=1,
            sponsorship={"relationship": "gifted", "sponsors": ["Brand"]},
        )
        db.add(row)
        db.commit()
        db.expire_all()
        assert db.get(Analysis, row.id).sponsorship["relationship"] == "gifted"


def test_disclosure_for_a_different_named_sponsor_is_not_reused():
    from app.analysis.disclosure import sponsor_disclosed

    assert not caption_disclosure("Sponsored by Alpha.", ["Beta"])
    assert not sponsor_disclosed("Sponsored by Alpha.", ["Beta"], multiple=False)


def test_invalid_sponsorship_is_rejected_by_upload_and_import_api():
    import uuid

    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_db] = lambda: None
    client = TestClient(app)
    response = client.post(
        "/api/analyses",
        files={"file": ("clip.mp4", b"fake")},
        data={
            "platform": "youtube_shorts",
            "language": "en",
            "sponsorship": '{"relationship":"invalid"}',
        },
    )
    assert response.status_code == 422
    response = client.post(
        "/api/analyses/import",
        json={
            "connection_id": str(uuid.uuid4()),
            "media_id": "123",
            "sponsorship": {"relationship": "invalid"},
        },
    )
    assert response.status_code == 422
