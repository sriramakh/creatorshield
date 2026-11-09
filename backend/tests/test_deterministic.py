from __future__ import annotations

from typing import Any

from app.analysis.deterministic import run_deterministic_checks
from app.analysis.risk import compute_risk


def extraction(
    segments: list[str] | None = None,
    ocr: list[str] | None = None,
    non_speech: list[list[float]] | None = None,
) -> dict[str, Any]:
    return {
        "transcript": {
            "segments": [
                {"id": f"T{i + 1}", "start": i * 3.0, "end": i * 3.0 + 3, "text": t}
                for i, t in enumerate(segments or [])
            ]
        },
        "ocr": [
            {"id": f"O{i + 1}", "frame_id": "F1", "timestamp": 5.0 + i, "text": t}
            for i, t in enumerate(ocr or [])
        ],
        "audio": {"non_speech_sound_intervals": non_speech or []},
    }


def titles(findings: list[Any]) -> list[str]:
    return [f.title for f in findings]


def test_promo_without_disclosure_is_flagged_with_timestamp() -> None:
    out = run_deterministic_checks(
        "youtube_shorts", "", [], extraction(["hello", "use my code FIT50 for 50% off"]), 20
    )
    f = next(f for f in out if f.category == "disclosure" and f.finding_type != "cannot_check")
    assert f.finding_type == "suspected_violation"
    assert f.start_seconds == 3.0
    assert "YT-DISC-PAID-PROMO" in f.policy_rule_ids


def test_promo_with_disclosure_is_not_flagged() -> None:
    out = run_deterministic_checks(
        "instagram_reels",
        "#ad Paid partnership with FitFuel",
        [],
        extraction(["use my code FIT50"]),
        20,
    )
    assert not [f for f in out if f.category == "disclosure" and f.finding_type != "cannot_check"]


def test_hindi_promo_and_guarantee_variants() -> None:
    out = run_deterministic_checks(
        "instagram_reels",
        "",
        [],
        extraction(["इस क्रीम से चेहरा गोरा हो जाएगा, गारन्ती है।", "मेरा कोड इस्तेमाल करें"]),
        20,
    )
    cats = {f.category for f in out if f.finding_type != "cannot_check"}
    assert {"disclosure", "spam_deception"} <= cats


def test_youtube_hashtag_limit() -> None:
    tags = [f"tag{i}" for i in range(61)]
    out = run_deterministic_checks("youtube_shorts", "", tags, extraction(), 20)
    assert any("exceeds YouTube's limit of 60" in t for t in titles(out))
    out = run_deterministic_checks("youtube_shorts", "", tags[:60], extraction(), 20)
    assert not any("limit of 60" in t for t in titles(out))


def test_watermark_detected_in_ocr() -> None:
    out = run_deterministic_checks(
        "instagram_reels", "", [], extraction(ocr=["TikTok @someone"]), 20
    )
    assert any(f.category == "originality" for f in out)


def test_non_speech_audio_produces_licensing_uncertainty_not_a_verdict() -> None:
    out = run_deterministic_checks(
        "youtube_shorts", "", [], extraction(non_speech=[[21.0, 27.0], [1.0, 2.0]]), 27
    )
    f = next(f for f in out if f.finding_type == "licensing_uncertainty")
    assert (f.start_seconds, f.end_seconds) == (21.0, 27.0)
    assert "does NOT mean" in f.explanation


def test_cannot_check_items_always_present_and_clean_video_is_low_risk() -> None:
    out = run_deterministic_checks(
        "youtube_shorts",
        "Three stretches after a workout",
        ["fitness"],
        extraction(["here are three stretches"]),
        20,
    )
    assert [f.finding_type for f in out] == ["cannot_check", "cannot_check"]
    score, level = compute_risk(out)
    assert (score, level) == (0, "low")


def test_risk_levels() -> None:
    class F:
        def __init__(
            self, severity: str, ftype: str = "observed_evidence", confidence: str = "high"
        ) -> None:
            self.severity, self.finding_type, self.confidence = severity, ftype, confidence

    assert compute_risk([F("critical")])[1] == "high"
    assert compute_risk([F("high")])[1] == "elevated"
    assert compute_risk([F("medium")])[1] == "moderate"
    assert compute_risk([F("high", confidence="low")])[1] == "moderate"
    assert compute_risk([F("critical", "cannot_check")]) == (0, "low")
