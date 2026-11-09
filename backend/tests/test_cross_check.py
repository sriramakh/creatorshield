from __future__ import annotations

from app.analysis.cross_check import _tokens, build_cross_check
from app.analysis.deterministic import run_deterministic_checks
from app.analysis.risk import compute_risk


def _segments(text: str) -> list[dict[str, object]]:
    return [{"id": "T1", "start": 0.0, "end": 3.0, "text": text}]


def _extraction(text: str, non_speech: list[list[float]] | None = None) -> dict[str, object]:
    return {
        "transcript": {"segments": _segments(text)},
        "ocr": [{"id": "O1", "text": "morning routine protein"}],
        "audio": {"non_speech_sound_intervals": non_speech or []},
    }


def test_matching_duration_and_captions_add_no_mismatch_finding() -> None:
    speech = "this is my morning routine with protein and a short walk outside today"
    report, findings = build_cross_check(
        "youtube_shorts",
        {
            "original_file_duration_seconds": 27.2,
            "analysed_duration_seconds": 27.2,
            "platform_duration_seconds": 27.0,
            "caption_segments": _segments(speech),
            "thumbnail_text": "",
            "platform_withheld_media": False,
            "platform_offered_file": False,
        },
        _extraction(speech),
    )
    assert report["duration_status"] == "match"
    assert report["caption_track_status"] == "match"
    assert findings == []
    assert report["file_matches_post"] == "yes"
    assert any(line["label"] == "Copyright match" for line in report["lines"])


HINDI = "नमस्ते दोस्तों आज मैं आपको अपनी सुबह की दिनचर्या दिखाने वाला हूँ जिसमें प्रोटीन शेक और योग शामिल है"


def test_hindi_words_are_not_split_at_vowel_signs() -> None:
    tokens = _tokens(HINDI)
    assert "नमस्ते" in tokens
    assert "दिनचर्या" in tokens
    assert len(tokens) >= 15


def test_identical_hindi_caption_track_matches() -> None:
    report, findings = build_cross_check(
        "youtube_shorts",
        {
            "original_file_duration_seconds": 20.0,
            "analysed_duration_seconds": 20.0,
            "platform_duration_seconds": 20.0,
            "caption_segments": _segments(HINDI),
            "thumbnail_text": "",
            "platform_withheld_media": False,
        },
        _extraction(HINDI),
    )
    assert report["caption_track_status"] == "match"
    assert findings == []


def test_duration_and_caption_mismatch_are_flagged() -> None:
    report, findings = build_cross_check(
        "youtube_shorts",
        {
            "original_file_duration_seconds": 12.0,
            "analysed_duration_seconds": 12.0,
            "platform_duration_seconds": 58.0,
            "caption_segments": _segments(
                "a completely different caption track about baking bread at home tonight"
            ),
            "thumbnail_text": "",
            "platform_withheld_media": False,
        },
        _extraction("buy the serum now and use my code for the limited offer today"),
    )
    assert report["duration_status"] == "mismatch"
    assert report["caption_track_status"] == "mismatch"
    assert report["file_matches_post"] == "no"
    # A wrong file is a report-validity problem, not a policy risk.
    assert findings == []
    assert compute_risk(findings) == (0, "low")


def test_trimmed_file_that_matches_the_platform_is_not_a_mismatch() -> None:
    report, findings = build_cross_check(
        "instagram_reels",
        {
            "original_file_duration_seconds": 90.0,
            "analysed_duration_seconds": 60.0,
            "platform_duration_seconds": 90.0,
            "caption_segments": [],
            "thumbnail_text": "",
            "platform_withheld_media": False,
            "platform_offered_file": True,
        },
        _extraction("hello there friend how are you doing on this fine morning"),
    )
    assert report["duration_status"] == "trimmed"
    assert not any("length does not match" in f.title for f in findings)


def test_withheld_instagram_file_is_cross_checked_against_audio() -> None:
    speech = "hello there friend how are you doing on this fine morning"
    _report, with_music = build_cross_check(
        "instagram_reels",
        {
            "original_file_duration_seconds": 20,
            "analysed_duration_seconds": 20,
            "platform_duration_seconds": None,
            "caption_segments": [],
            "thumbnail_text": "",
            "platform_withheld_media": True,
        },
        _extraction(speech, non_speech=[[0.0, 8.0]]),
    )
    music = next(f for f in with_music if f.category == "licensing")
    assert music.severity == "low"
    assert "IG-COPYRIGHT" in music.policy_rule_ids
    assert "not, by itself, a violation" in music.explanation

    _report, without_music = build_cross_check(
        "instagram_reels",
        {
            "original_file_duration_seconds": 20,
            "analysed_duration_seconds": 20,
            "platform_duration_seconds": None,
            "caption_segments": [],
            "thumbnail_text": "",
            "platform_withheld_media": True,
        },
        _extraction(speech),
    )
    quiet = next(f for f in without_music if f.category == "licensing")
    # Weaker evidence must not rank above the case with music present.
    assert quiet.severity == "low"
    assert quiet.confidence == "low"


def test_cover_text_missing_from_the_video_is_flagged() -> None:
    report, findings = build_cross_check(
        "instagram_reels",
        {
            "original_file_duration_seconds": 20,
            "analysed_duration_seconds": 20,
            "platform_duration_seconds": None,
            "caption_segments": [],
            "thumbnail_text": "GUARANTEED FAIR SKIN OVERNIGHT MIRACLE",
            "platform_withheld_media": False,
            "platform_offered_file": True,
        },
        _extraction("hello there friend how are you doing on this fine morning"),
    )
    assert report["thumbnail_text_status"] == "mismatch"
    cover = next(f for f in findings if f.category == "spam_deception")
    assert cover.policy_rule_ids == ["META-CS-SPAM"]


def test_cross_checked_mode_still_reviews_the_file() -> None:
    findings = run_deterministic_checks(
        "youtube_shorts",
        "",
        [],
        {"transcript": {"segments": []}, "ocr": [], "audio": {}},
        20,
        analysis_mode="cross_checked",
    )
    titles = [f.title for f in findings]
    assert "Video frames, speech and audio were not analysed" not in titles
    assert "Platform copyright matching (Content ID, Rights Manager) was not performed" in titles
