"""Community-guideline risk flags: wording only, cited to official pages."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.analysis.deterministic import run_deterministic_checks
from app.config import get_settings
from app.policies.kb import load_kb
from app.reports.render import render_html
from app.reports.sections import section_for
from app.schemas import AnalysisOut, FindingOut, PolicyRef
from tests.test_deterministic import extraction


def _flags(platform: str, segments: list[str] | None = None, **kwargs: object) -> list:
    caption = kwargs.pop("caption", "")
    ocr = kwargs.pop("ocr", None)
    out = run_deterministic_checks(
        platform,
        str(caption),
        [],
        extraction(segments, ocr=ocr if isinstance(ocr, list) else None),
        30,
    )
    return [
        f for f in out if f.category == "community_guidelines" and f.finding_type != "cannot_check"
    ]


def _titled(findings: list, title_part: str):
    return next(f for f in findings if title_part in f.title)


def test_clean_video_has_no_community_guideline_flag() -> None:
    assert _flags("youtube_shorts", ["here are three stretches"]) == []


def test_finance_claim_is_a_timestamped_risk_flag_and_not_a_medical_citation() -> None:
    flags = _flags("youtube_shorts", ["hello", "these are guaranteed returns of 20 percent"])
    flag = _titled(flags, "guaranteed-returns")
    assert flag.severity == "high"
    assert flag.start_seconds == 3.0
    assert flag.policy_rule_ids == ["YT-CG-SPAM", "YT-MON-AD-FRIENDLY"]
    assert "YT-CG-MEDMISINFO" not in flag.policy_rule_ids
    assert "IN-ASCI-INFLUENCER" not in flag.policy_rule_ids
    assert flag.explanation.startswith("Risk flag only:")
    assert "not a decision" in flag.explanation
    # The older absolute-claim check must not describe this as a cure.
    out = run_deterministic_checks(
        "youtube_shorts",
        "",
        [],
        extraction(["these are guaranteed returns of 20 percent"]),
        30,
    )
    assert not [
        f for f in out if f.category == "spam_deception" and f.finding_type != "cannot_check"
    ]


def test_instagram_finance_cites_meta_not_youtube() -> None:
    flag = _titled(_flags("instagram_reels", ["double your money this week"]), "guaranteed-returns")
    assert flag.policy_rule_ids == ["META-CS-COMMERCIAL", "META-CS-SPAM"]


def test_hindi_returns_claim() -> None:
    flag = _titled(_flags("youtube_shorts", ["गारंटी रिटर्न मिलेगा"]), "guaranteed-returns")
    assert "YT-CG-SPAM" in flag.policy_rule_ids


def test_cure_claim_stays_a_medical_signal_inside_the_community_section() -> None:
    out = run_deterministic_checks(
        "youtube_shorts", "", [], extraction(["this drink cures cancer"]), 20
    )
    medical = [
        f for f in out if f.category == "spam_deception" and f.finding_type != "cannot_check"
    ]
    assert len(medical) == 1
    assert section_for(medical[0].category, medical[0].policy_rule_ids) == "community"
    assert "YT-CG-MEDMISINFO" in medical[0].policy_rule_ids
    extra = _flags("youtube_shorts", ["this drink cures cancer"])
    assert [f for f in extra if "medical" in f.title] == []


def test_vaccine_claim_is_its_own_medical_flag() -> None:
    flag = _titled(_flags("youtube_shorts", ["vaccines cause autism"]), "medical misinformation")
    assert flag.start_seconds == 0.0
    assert "YT-CG-MEDMISINFO" in flag.policy_rule_ids
    assert flag.requires_human_review is True


def test_election_opinion_is_not_flagged_but_a_voting_instruction_is() -> None:
    assert _flags("youtube_shorts", ["the election was stolen and rigged"]) == []
    flag = _titled(_flags("instagram_reels", ["you can vote by texting 55512"]), "election")
    assert flag.policy_rule_ids == ["META-CS-MISINFO"]
    assert flag.severity == "high"


def test_child_sexual_wording_is_critical_even_with_a_documentary_label() -> None:
    flag = _titled(
        _flags("youtube_shorts", ["a documentary about underage porn"]),
        "minor",
    )
    assert flag.severity == "critical"
    assert flag.context_exception is None
    assert flag.policy_rule_ids == ["YT-CG-CHILD"]


def test_documentary_context_lowers_a_hate_flag_without_dropping_it() -> None:
    plain = _titled(_flags("youtube_shorts", ["kill all muslims"]), "hate")
    assert plain.severity == "high" and plain.context_exception is None
    quoted = _titled(
        _flags("youtube_shorts", ["in this documentary we examine the line kill all muslims"]),
        "hate",
    )
    assert quoted.severity == "medium"
    assert quoted.context_exception


def test_slur_is_a_hate_flag() -> None:
    flag = _titled(_flags("instagram_reels", ["he called them kikes"]), "hate")
    assert "META-CS-HATE" in flag.policy_rule_ids


def test_everyday_phrases_are_not_flags() -> None:
    text = [
        "this killer workout will kill your excuses",
        "nude lipstick shade for the office",
        "the election was stolen",
        "buy a water gun for the kids",
        "I smoke fags",  # UK cigarette; not a slur and not a sale
        "order a beer after the match",
        "please don't kill yourself, here is a helpline",
    ]
    assert _flags("youtube_shorts", text) == []


def test_firearm_sale_and_copyright_disclaimer_are_separate_flags() -> None:
    flags = _flags(
        "youtube_shorts",
        ocr=["DM to buy a Glock", "no copyright infringement intended"],
    )
    gun = _titled(flags, "firearm")
    copy = _titled(flags, "copyright")
    assert gun.severity == "high"
    assert "YT-CG-FIREARMS" in gun.policy_rule_ids
    assert gun.start_seconds == 5.0
    assert copy.severity == "low"
    assert "YT-COPY-BASICS" in copy.policy_rule_ids
    assert "does not mean you lack a licence" in copy.explanation


def test_packs_cite_only_rules_that_exist_for_the_platform() -> None:
    from app.analysis.community_guidelines import PACKS

    kb = load_kb(get_settings().policy_kb_path)
    assert kb.version == "2026.11.28"
    assert len([r for r in kb.rules if r.platform in {"youtube", "instagram", "meta_all"}]) == 41
    for rule_id in (
        "YT-CG-CHILD",
        "YT-CG-ELECTIONS",
        "YT-CG-FIREARMS",
        "META-CS-CHILD",
        "META-CS-RESTRICTED",
    ):
        rule = kb.get(rule_id)
        assert rule is not None
        assert rule.official_url.host in {"support.google.com", "transparency.meta.com"}
    for platform in ("youtube_shorts", "instagram_reels"):
        for pack in PACKS:
            ids = pack.rule_ids(platform)
            assert ids, pack.key
            for rule_id in ids:
                assert kb.applies(rule_id, platform), f"{pack.key} {rule_id} {platform}"


def test_report_splits_community_guidelines_from_disclosure() -> None:
    now = datetime.now(UTC)
    aid = uuid.uuid4()

    def finding(**overrides: object) -> FindingOut:
        data: dict[str, object] = {
            "id": uuid.uuid4(),
            "source": "deterministic",
            "category": "community_guidelines",
            "category_label": "Community guidelines",
            "finding_type": "suspected_violation",
            "severity": "high",
            "confidence": "medium",
            "title": "Risk flag: possible get-rich-quick or guaranteed-returns claim",
            "explanation": "Risk flag only: example.",
            "suggested_action": "Remove the guaranteed-return line.",
            "start_seconds": 4.0,
            "end_seconds": 7.0,
            "evidence": [
                {
                    "source": "transcript",
                    "ref_id": "T2",
                    "detail": "guaranteed returns",
                    "timestamp": 4.0,
                }
            ],
            "policy_rule_ids": ["YT-CG-SPAM", "YT-MON-AD-FRIENDLY"],
            "policies": [
                PolicyRef(
                    id="YT-CG-SPAM",
                    platform="youtube",
                    title="Spam, deceptive practices & scams",
                    official_title="Spam Policy",
                    official_url="https://support.google.com/youtube/answer/2801973",
                    verified_on="2026-10-21",
                )
            ],
            "context_exception": None,
            "requires_human_review": True,
            "validation_notes": [],
        }
        data.update(overrides)
        return FindingOut.model_validate(data)

    disclosure = finding(
        category="disclosure",
        category_label="Sponsored-content disclosure",
        title="Promotional language without a visible sponsorship disclosure",
        policy_rule_ids=["YT-DISC-PAID-PROMO"],
        policies=[
            PolicyRef(
                id="YT-DISC-PAID-PROMO",
                platform="youtube",
                title="Paid product placements",
                official_title="Add branded content restrictions & disclosure labels",
                official_url="https://support.google.com/youtube/answer/154235",
                verified_on="2026-10-21",
            )
        ],
    )
    licensing = finding(
        category="licensing",
        category_label="Music & third-party licensing",
        title="Non-speech audio",
        severity="low",
        policy_rule_ids=["YT-COPY-BASICS"],
        policies=[],
    )
    html = render_html(
        AnalysisOut(
            id=aid,
            created_at=now,
            updated_at=now,
            expires_at=now,
            status="completed",
            stage="completed",
            progress=100,
            platform="youtube_shorts",
            language="en",
            caption="",
            duration_seconds=20,
            risk_level="elevated",
            risk_score=22,
            mock_mode=False,
            source="upload",
            error_message=None,
            hashtags=[],
            file_ext="mp4",
            content_type="video/mp4",
            size_bytes=10,
            media_deleted=False,
            media_info=None,
            extraction=None,
            ai_provider=None,
            ai_model=None,
            ai_status="skipped",
            ai_status_detail=None,
            policy_kb_version="2026.11.26",
            summary=None,
            context_assessment=None,
            limitations=["Imagery is not classified."],
            findings=[finding(), disclosure, licensing],
        )
    )
    community_at = html.index('id="community-guidelines"')
    disclosure_at = html.index('id="disclosure"')
    assert community_at < disclosure_at
    assert html.index("guaranteed-returns") < disclosure_at
    assert html.index("Promotional language") > disclosure_at
    assert "Suggested fix" in html
    assert "https://support.google.com/youtube/answer/2801973" in html
    assert "Other findings" in html
    assert "does not classify imagery" in html


# --- Regressions from the analysis-engine review -------------------------------


def test_innocent_child_wording_is_not_critical() -> None:
    assert _flags("youtube_shorts", ["My kids are my only fans haha"]) == []
    bath = _flags("youtube_shorts", ["my kid ran around the house naked after bath time"])
    flag = _titled(bath, "minor")
    # Still surfaced for a person to judge, but not as an automatic critical.
    assert flag.severity == "medium" and flag.confidence == "low"
    assert flag.requires_human_review
    from app.analysis.risk import compute_risk

    assert compute_risk(bath)[1] in {"low", "moderate"}


def test_explicit_child_sexual_wording_stays_critical() -> None:
    for line in [
        "child porn links in bio",
        "kid porn",
        "underage nudes for sale",
        "nude photos of a child",
        "sexy little girl dancing",
        "sexy kids compilation",
        "my kid has an onlyfans account",
        "onlyfans account for 15 year olds",
    ]:
        flag = _titled(_flags("instagram_reels", [line]), "minor")
        assert flag.severity == "critical" and flag.confidence == "high", line


def test_everyday_wording_is_not_a_risk_flag() -> None:
    assert (
        _flags(
            "youtube_shorts",
            [
                "Buying Top Gun Maverick on blu-ray",
                "Guns N Roses tickets for sale",
                "buying a nerf gun for my nephew",
                "buy a bottle of white wine for this risotto",
                "Don’t kill yourself over this exam, take a break",
            ],
        )
        == []
    )


def test_gaming_talk_is_lowered_not_dropped() -> None:
    threat = _titled(_flags("youtube_shorts", ["I'm gonna kill you in this round lol"]), "threat")
    assert threat.severity == "low"
    hate = _titled(_flags("youtube_shorts", ["kill all the men in this level of the game"]), "hate")
    assert hate.severity == "low"
    # Outside a game the same wording keeps its severity.
    assert _titled(_flags("youtube_shorts", ["I'm gonna kill you"]), "threat").severity == "high"


def test_real_sales_still_flag() -> None:
    assert _titled(_flags("youtube_shorts", ["Selling glock 19, dm me"]), "firearm")
    assert _titled(_flags("youtube_shorts", ["buy whisky, dm me for delivery"]), "alcohol")


def test_typographic_apostrophe_matches_like_ascii() -> None:
    assert _titled(_flags("youtube_shorts", ["you should kill yourself"]), "suicide")
    assert _flags("youtube_shorts", ["Please don’t ever kill yourself"]) == []


def test_thumbnail_ocr_profanity_is_not_escalated_as_early() -> None:
    out = run_deterministic_checks(
        "instagram_reels",
        "",
        [],
        {
            "transcript": {"segments": []},
            "frames": [{"id": "F1", "timestamp": 0.0, "reason": "thumbnail", "file": "F1.jpg"}],
            "ocr": [{"id": "O1", "frame_id": "F1", "timestamp": 0.0, "text": "what the fuck"}],
        },
        0.0,
        analysis_mode="caption_thumbnail",
    )
    flag = _titled([f for f in out if f.category == "community_guidelines"], "strong language")
    assert flag.severity == "low"
    assert flag.start_seconds is None and flag.evidence[0]["timestamp"] is None
