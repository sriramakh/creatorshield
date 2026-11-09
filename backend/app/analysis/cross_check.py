"""Cross-check an owner-supplied file against what the platform reports.

The file is the creator's own export (YouTube Studio, Instagram's data download,
or the original upload). This module never fetches platform audiovisual content.
It also cannot name a track or query Content ID / Rights Manager. A match here
is evidence the file lines up with the published post, not a copyright clearance.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from app.analysis.deterministic import PLATFORM_RULES
from app.schemas import FindingDraft

_MIN_TOKENS = 8
_DURATION_FLOOR_SECONDS = 1.5
_DURATION_RATIO = 0.08

SPAM_RULES = {
    "youtube_shorts": ["YT-CG-SPAM"],
    "instagram_reels": ["META-CS-SPAM"],
}


def _is_word_char(ch: str) -> bool:
    # Devanagari vowel signs and the virama are combining marks (category M*),
    # not alphanumerics, so a plain \w regex would split Hindi words apart.
    return ch.isalnum() or unicodedata.category(ch).startswith("M")


def _tokens(text: str) -> set[str]:
    words: set[str] = set()
    current: list[str] = []
    for ch in (text or "") + " ":
        if _is_word_char(ch):
            current.append(ch)
            continue
        if len(current) >= 2:
            words.add("".join(current).casefold())
        current = []
    return words


def _overlap(left: set[str], right: set[str]) -> float | None:
    """Share of the smaller set that also appears in the larger one."""
    if len(left) < _MIN_TOKENS or len(right) < _MIN_TOKENS:
        return None
    return len(left & right) / min(len(left), len(right))


def _join(segments: list[dict[str, Any]] | None) -> str:
    return " ".join(str(segment.get("text") or "") for segment in segments or [])


def _duration_status(platform: float | None, original: float, analysed: float) -> str:
    if platform is None:
        return "unknown"
    tolerance = max(_DURATION_FLOOR_SECONDS, _DURATION_RATIO * platform)
    if abs(platform - original) <= tolerance:
        if analysed + 0.5 < original:
            return "trimmed"
        return "match"
    return "mismatch"


def _line(label: str, status: str, detail: str) -> dict[str, str]:
    return {"label": label, "status": status, "detail": detail}


def build_cross_check(
    platform: str,
    snapshot: dict[str, Any],
    extraction: dict[str, Any],
) -> tuple[dict[str, Any], list[FindingDraft]]:
    """Return a report dict (safe to show and to pass to the model) and findings."""
    rules = PLATFORM_RULES[platform]
    original = float(snapshot.get("original_file_duration_seconds") or 0)
    analysed = float(snapshot.get("analysed_duration_seconds") or original)
    platform_duration = snapshot.get("platform_duration_seconds")
    platform_seconds = (
        float(platform_duration) if isinstance(platform_duration, (int, float)) else None
    )
    duration_status = _duration_status(platform_seconds, original, analysed)

    file_text = _join((extraction.get("transcript") or {}).get("segments"))
    file_tokens = _tokens(file_text)
    caption_tokens = _tokens(_join(snapshot.get("caption_segments")))
    caption_overlap = _overlap(caption_tokens, file_tokens)
    if not snapshot.get("caption_segments"):
        caption_status = "unavailable"
    elif caption_overlap is None:
        caption_status = "insufficient"
    elif caption_overlap >= 0.55:
        caption_status = "match"
    elif caption_overlap < 0.30:
        caption_status = "mismatch"
    else:
        caption_status = "partial"

    video_tokens = file_tokens | _tokens(
        " ".join(str(item.get("text") or "") for item in extraction.get("ocr") or [])
    )
    thumb_text = str(snapshot.get("thumbnail_text") or "")
    distinctive = {token for token in _tokens(thumb_text) if len(token) >= 4}
    if not thumb_text.strip():
        thumbnail_status = "unavailable"
        thumbnail_overlap = None
    elif len(distinctive) < 3:
        thumbnail_status = "insufficient"
        thumbnail_overlap = None
    else:
        thumbnail_overlap = len(distinctive & video_tokens) / len(distinctive)
        thumbnail_status = "match" if thumbnail_overlap >= 0.5 else "mismatch"

    intervals = (extraction.get("audio") or {}).get("non_speech_sound_intervals") or []
    non_speech = round(sum(float(b) - float(a) for a, b in intervals), 1)
    withheld = bool(snapshot.get("platform_withheld_media"))
    offered = bool(snapshot.get("platform_offered_file"))

    lines: list[dict[str, str]] = []
    findings: list[FindingDraft] = []
    notes: list[str] = []

    if duration_status == "match" and platform_seconds is not None:
        lines.append(
            _line(
                "Duration",
                "ok",
                f"The file is {original:.1f}s and the platform reports {platform_seconds:.1f}s.",
            )
        )
    elif duration_status == "trimmed" and platform_seconds is not None:
        lines.append(
            _line(
                "Duration",
                "warn",
                f"The file is {original:.1f}s, matching the platform's {platform_seconds:.1f}s. "
                f"Only the first {analysed:.0f}s were analysed.",
            )
        )
    elif duration_status == "mismatch" and platform_seconds is not None:
        lines.append(
            _line(
                "Duration",
                "bad",
                f"The file is {original:.1f}s; the platform reports {platform_seconds:.1f}s. "
                "This may be a different cut than the live post.",
            )
        )
    else:
        lines.append(
            _line(
                "Duration",
                "muted",
                "The platform did not report a duration, so the file length could not be "
                "checked against the live post.",
            )
        )

    if caption_status == "match" and caption_overlap is not None:
        lines.append(
            _line(
                "Speech vs captions",
                "ok",
                f"Words in the file overlap the platform caption track ({caption_overlap:.0%}).",
            )
        )
    elif caption_status == "partial" and caption_overlap is not None:
        lines.append(
            _line(
                "Speech vs captions",
                "warn",
                f"Only {caption_overlap:.0%} of the words overlap the platform caption track. "
                "One of the transcripts may be wrong, or this may not be the published cut.",
            )
        )
        notes.append(
            "Caption-track overlap was only partial. Speech recognition on either side can "
            "be wrong, particularly with music or Hindi."
        )
    elif caption_status == "mismatch" and caption_overlap is not None:
        lines.append(
            _line(
                "Speech vs captions",
                "bad",
                f"Only {caption_overlap:.0%} of the words overlap the platform caption track. "
                "The file likely is not the published cut.",
            )
        )
    elif caption_status == "insufficient":
        lines.append(
            _line(
                "Speech vs captions",
                "muted",
                "A caption track exists, but there is not enough speech in both transcripts "
                "to compare them.",
            )
        )
    else:
        lines.append(
            _line(
                "Speech vs captions",
                "muted",
                "No platform caption track was available, so speech was not compared with one. "
                "YouTube captions require the captions permission.",
            )
        )

    if thumbnail_status == "match":
        lines.append(
            _line(
                "Cover text",
                "ok",
                "Text on the platform cover also appears in the video or the transcript.",
            )
        )
    elif thumbnail_status == "mismatch":
        lines.append(
            _line(
                "Cover text",
                "warn",
                "Text read from the platform cover was not found in the sampled frames or "
                "the transcript. The cover may promise something the video does not show.",
            )
        )
        findings.append(
            FindingDraft(
                source="deterministic",
                category="spam_deception",
                finding_type="suspected_violation",
                severity="low",
                confidence="low",
                title="Cover text was not found in the video",
                explanation=(
                    "Text read from the cover image the platform returned did not appear in "
                    "the sampled frames or the spoken transcript. A cover that promises "
                    "something the video does not show can be treated as misleading. On-screen "
                    "text recognition misses stylised lettering, so confirm this visually."
                ),
                suggested_action=(
                    "Compare the cover with the video. Change the cover if it overstates what "
                    "the video shows."
                ),
                evidence=[
                    {
                        "source": "metadata",
                        "ref_id": "METADATA",
                        "detail": "Cover text did not match sampled frames or speech",
                        "timestamp": None,
                    }
                ],
                policy_rule_ids=SPAM_RULES.get(platform, []),
                requires_human_review=True,
            )
        )
    elif thumbnail_status == "insufficient":
        lines.append(
            _line(
                "Cover text",
                "muted",
                "The cover had too little readable text to compare with the video.",
            )
        )

    if withheld and non_speech >= 3:
        lines.append(
            _line(
                "Platform file",
                "warn",
                "Instagram withheld the video file, which it does for licensed audio "
                "(including its own library) or a copyright flag. The supplied file also "
                f"has about {non_speech:.0f}s of non-speech audio. The track was not identified.",
            )
        )
        findings.append(
            FindingDraft(
                source="deterministic",
                category="licensing",
                finding_type="licensing_uncertainty",
                severity="low",
                confidence="medium",
                title=(
                    "Instagram withheld the video file, and the supplied file has non-speech audio"
                ),
                explanation=(
                    "Instagram does not return a Reel's file when it contains licensed audio, "
                    "including tracks from Instagram's own audio library, or when the Reel was "
                    "flagged for copyright. Instagram does not say which. The file you supplied "
                    f"has about {non_speech:.0f}s of audio that is not speech. This tool cannot "
                    "name the track or tell whether you have a licence. Audio from Instagram's "
                    "library is allowed on Instagram and is not, by itself, a violation."
                ),
                suggested_action=(
                    "Open the Reel's audio details and confirm the source. Keep the licence if "
                    "the music is not from Instagram's library. If you cannot show a right to "
                    "use it, replace the audio."
                ),
                evidence=[
                    {
                        "source": "metadata",
                        "ref_id": "METADATA",
                        "detail": (
                            "Instagram withheld media_url; non-speech audio is present in the file"
                        ),
                        "timestamp": None,
                    }
                ],
                policy_rule_ids=rules["copyright"],
                requires_human_review=True,
            )
        )
    elif withheld:
        lines.append(
            _line(
                "Platform file",
                "warn",
                "Instagram withheld the video file (licensed or copyright-flagged audio are "
                "the usual reasons). The supplied file shows little non-speech audio, so the "
                "file may be a different cut or the music may sit under speech.",
            )
        )
        findings.append(
            FindingDraft(
                source="deterministic",
                category="licensing",
                finding_type="licensing_uncertainty",
                severity="low",
                confidence="low",
                title=(
                    "Instagram withheld the file, but the supplied file shows "
                    "little non-speech audio"
                ),
                explanation=(
                    "Instagram withholds the video file for licensed audio, including its own "
                    "library, or for a copyright flag, and does not say which. The file you "
                    "supplied does not show a clear stretch of non-speech audio. Speech-heavy "
                    "music can be missed, or this file may not be the published cut. Neither "
                    "result is a clearance, and neither is proof of a specific infringement."
                ),
                suggested_action=(
                    "Confirm this is the exact published file, then check the Reel's audio "
                    "details. Replace audio you cannot show a right to use."
                ),
                evidence=[
                    {
                        "source": "metadata",
                        "ref_id": "METADATA",
                        "detail": (
                            "Instagram withheld media_url; little non-speech audio in the file"
                        ),
                        "timestamp": None,
                    }
                ],
                policy_rule_ids=rules["copyright"],
                requires_human_review=True,
            )
        )
    elif offered:
        lines.append(
            _line(
                "Platform file",
                "ok",
                "Instagram can provide this Reel's file. This review used the file you "
                "supplied and checked it against the post.",
            )
        )
    else:
        lines.append(
            _line(
                "Platform file",
                "muted",
                "YouTube's API does not allow downloading the video. Frames, speech and "
                "audio in this review come from the file you supplied.",
            )
        )

    lines.append(
        _line(
            "Copyright match",
            "muted",
            "No Content ID or Rights Manager lookup was run. Catalogue, music and web "
            "checks are listed under provenance. No copyright finding does not mean the "
            "footage or music is cleared.",
        )
    )

    # A mismatch is about whether this report describes the live post, not a
    # policy risk, so it is reported as a verdict and kept out of the risk score.
    if duration_status == "mismatch" or caption_status == "mismatch":
        file_matches_post = "no"
    elif duration_status in {"match", "trimmed"} or caption_status == "match":
        file_matches_post = "partial" if caption_status == "partial" else "yes"
    else:
        file_matches_post = "unknown"

    report = {
        "file_matches_post": file_matches_post,
        "duration_status": duration_status,
        "platform_duration_seconds": platform_seconds,
        "original_file_duration_seconds": original,
        "analysed_duration_seconds": analysed,
        "caption_track_status": caption_status,
        "caption_track_overlap": None if caption_overlap is None else round(caption_overlap, 3),
        "thumbnail_text_status": thumbnail_status,
        "platform_withheld_media": withheld,
        "platform_offered_file": offered,
        "non_speech_seconds": non_speech,
        "lines": lines,
        "notes": notes,
    }
    return report, findings
