"""Rule-based checks that need no AI model.

These are deliberately conservative pattern checks. They produce *signals*
("possible undisclosed promotion"), never verdicts, and every finding they
emit cites a rule ID that must exist in the policy knowledge base (enforced by
tests and by validation at runtime).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.schemas import FindingDraft

PLATFORM_RULES: dict[str, dict[str, list[str]]] = {
    "youtube_shorts": {
        "disclosure": ["YT-DISC-PAID-PROMO", "IN-ASCI-INFLUENCER"],
        "copyright": ["YT-COPY-BASICS"],
        "hashtags": ["YT-HASHTAGS"],
        "health_claims": ["YT-MON-AD-FRIENDLY", "YT-CG-MEDMISINFO", "IN-ASCI-INFLUENCER"],
        "reused": ["YT-MON-YPP"],
    },
    "instagram_reels": {
        "disclosure": ["IG-PAID-PARTNERSHIP", "IG-BRANDED-DISCLOSURE", "IN-ASCI-INFLUENCER"],
        "copyright": ["IG-COPYRIGHT"],
        "hashtags": [],
        "health_claims": ["IG-MON-CONTENT", "IG-RECOMMENDATIONS", "IN-ASCI-INFLUENCER"],
        "reused": ["IG-MON-CONTENT", "IG-RECOMMENDATIONS"],
    },
}

# Promotion signals (English, Hindi, and common Hinglish transliterations).
_PROMO_PATTERNS = [
    r"\b(?:use|apply)\s+(?:my\s+)?(?:promo\s+|discount\s+|coupon\s+)?code\b",
    r"\bcode\s+[A-Z0-9]{3,}\b",
    r"\b(?:promo|discount|coupon)\s+code\b",
    r"\b\d{1,3}\s?%\s?off\b",
    r"\blink\s+(?:is\s+)?in\s+(?:my\s+)?bio\b",
    r"\baffiliate\b",
    r"\bsponsored\s+by\b",
    r"\bin\s+partnership\s+with\b",
    r"\bgifted\s+by\b",
    r"\bswipe\s+up\b",
    r"\bshop\s+now\b",
    r"कोड",
    r"(?:छूट|डिस्काउंट)",
    r"लिंक\s+बायो",
]
_DISCLOSURE_PATTERNS = [
    r"#ad\b",
    r"#advert(?:isement)?\b",
    r"#sponsored\b",
    r"#paidpartnership\b",
    r"#partner\b",
    r"#collab\b",
    r"\bpaid\s+partnership\b",
    r"\bsponsored\b(?!\s+by\b)",
    r"\bthis\s+(?:video|post|reel)\s+is\s+sponsored\b",
    r"\bsponsored\s+by\b",
    r"\b(?:ad|advertisement)\s*[:|-]",
    r"\bgifted\b",
    r"\baffiliate\s+link",
    r"विज्ञापन",
    r"प्रायोजित",
]
_HEALTH_CLAIM_PATTERNS = [
    r"\bcure[sd]?\b",
    r"\bguarantee[sd]?\b",
    r"\b100\s?%\s+(?:results|effective|guaranteed)\b",
    r"\bdoctors\s+(?:hate|don'?t\s+want)\b",
    r"\bmiracle\b",
    r"\blose\s+\d+\s*(?:kg|kgs|pounds|lbs)\b",
    r"\bpermanent(?:ly)?\s+(?:fix|cure)\b",
    r"गार(?:ं|न्)?[टत]ी",  # गारंटी / गारन्टी / गारन्ती (ASR spelling variants)
    r"इलाज",
    r"गोरा",
]
_WATERMARK_PATTERNS = [
    r"\btik\s?tok\b",
    r"\bcapcut\b",
    r"\bsnack\s?video\b",
    r"\bmoj\b",
    r"\bjosh\b",
]

_PROMO_RE = [re.compile(p, re.IGNORECASE) for p in _PROMO_PATTERNS]
_DISCLOSURE_RE = [re.compile(p, re.IGNORECASE) for p in _DISCLOSURE_PATTERNS]
_HEALTH_RE = [re.compile(p, re.IGNORECASE) for p in _HEALTH_CLAIM_PATTERNS]
_WATERMARK_RE = [re.compile(p, re.IGNORECASE) for p in _WATERMARK_PATTERNS]

YOUTUBE_HASHTAG_LIMIT = 60
MUSIC_MIN_SECONDS = 3.0


@dataclass
class TextItem:
    source: str  # transcript | ocr | caption | hashtags
    ref_id: str
    text: str
    start: float | None
    end: float | None


def collect_text_items(
    caption: str, hashtags: list[str], extraction: dict[str, Any]
) -> list[TextItem]:
    items: list[TextItem] = []
    if caption.strip():
        items.append(TextItem("caption", "CAPTION", caption, None, None))
    if hashtags:
        items.append(
            TextItem("hashtags", "HASHTAGS", " ".join(f"#{h}" for h in hashtags), None, None)
        )
    for seg in (extraction.get("transcript") or {}).get("segments", []):
        items.append(TextItem("transcript", seg["id"], seg["text"], seg["start"], seg["end"]))
    for o in extraction.get("ocr") or []:
        items.append(TextItem("ocr", o["id"], o["text"], o["timestamp"], o["timestamp"]))
    return items


def _matches(items: list[TextItem], patterns: list[re.Pattern[str]]) -> list[tuple[TextItem, str]]:
    hits: list[tuple[TextItem, str]] = []
    for item in items:
        for pat in patterns:
            m = pat.search(item.text)
            if m:
                hits.append((item, m.group(0)))
                break
    return hits


def _evidence(hits: list[tuple[TextItem, str]], limit: int = 6) -> list[dict[str, Any]]:
    return [
        {
            "source": item.source,
            "ref_id": item.ref_id,
            "detail": f'"{match}" in: {item.text[:160]}',
            "timestamp": item.start,
        }
        for item, match in hits[:limit]
    ]


def _span(hits: list[tuple[TextItem, str]]) -> tuple[float | None, float | None]:
    times = [(i.start, i.end) for i, _ in hits if i.start is not None]
    if not times:
        return None, None
    return min(t[0] for t in times if t[0] is not None), max(
        t[1] for t in times if t[1] is not None
    )


def run_deterministic_checks(
    platform: str,
    caption: str,
    hashtags: list[str],
    extraction: dict[str, Any],
    duration: float,
    analysis_mode: str = "full_video",
) -> list[FindingDraft]:
    rules = PLATFORM_RULES[platform]
    items = collect_text_items(caption, hashtags, extraction)
    findings: list[FindingDraft] = []

    # 1. Promotion signals without a visible disclosure ------------------------
    promo_hits = _matches(items, _PROMO_RE)
    disclosure_hits = _matches(items, _DISCLOSURE_RE)
    if promo_hits and not disclosure_hits:
        start, end = _span(promo_hits)
        label = (
            "YouTube's paid promotion setting"
            if platform == "youtube_shorts"
            else "Instagram's Paid partnership label"
        )
        findings.append(
            FindingDraft(
                source="deterministic",
                category="disclosure",
                finding_type="suspected_violation",
                severity="medium",
                confidence="medium",
                title="Promotional language without a visible sponsorship disclosure",
                explanation=(
                    "The caption, speech or on-screen text contains promotion signals (discount "
                    "codes, 'link in bio', percentage-off offers) but no disclosure such as "
                    "#ad, 'paid partnership' or 'sponsored' was found. If you received payment, "
                    "free products, commission or any other benefit, the platform expects this "
                    "to be disclosed. This check cannot tell whether a commercial relationship "
                    "actually exists."
                ),
                suggested_action=(
                    f"If this is a paid, gifted or affiliate promotion, enable {label} when "
                    "publishing and add a clear disclosure (e.g. #ad / 'Paid partnership') at "
                    "the start of the caption and on screen. Indian creators should also follow "
                    "ASCI influencer advertising guidelines."
                ),
                start_seconds=start,
                end_seconds=end,
                evidence=_evidence(promo_hits),
                policy_rule_ids=rules["disclosure"],
                requires_human_review=True,
            )
        )

    # 2. Strong efficacy / guarantee claims ----------------------------------
    health_hits = _matches([i for i in items if i.source != "hashtags"], _HEALTH_RE)
    if health_hits:
        start, end = _span(health_hits)
        findings.append(
            FindingDraft(
                source="deterministic",
                category="spam_deception",
                finding_type="observed_evidence",
                severity="medium",
                confidence="medium",
                title="Absolute claims detected ('cure', 'guaranteed', 'miracle')",
                explanation=(
                    "Words such as 'cure', 'guaranteed' or 'doctors don't want you to know' "
                    "appear in the content. Health or results claims stated as certain can be "
                    "treated as misleading, may limit ads or recommendations, and for medical "
                    "topics can conflict with health-misinformation policies. Whether a claim "
                    "is actually prohibited depends on the specific claim and context."
                ),
                suggested_action=(
                    "Remove absolute or guaranteed-outcome language, describe personal "
                    "experience as personal ('this helped me'), and avoid implying a product "
                    "treats or cures a medical condition unless substantiated."
                ),
                start_seconds=start,
                end_seconds=end,
                evidence=_evidence(health_hits),
                policy_rule_ids=rules["health_claims"],
                requires_human_review=True,
            )
        )

    # 3. YouTube hashtag limit -------------------------------------------------
    if platform == "youtube_shorts" and len(hashtags) > YOUTUBE_HASHTAG_LIMIT:
        findings.append(
            FindingDraft(
                source="deterministic",
                category="spam_deception",
                finding_type="observed_evidence",
                severity="medium",
                confidence="high",
                title=f"{len(hashtags)} hashtags exceeds YouTube's limit of 60",
                explanation=(
                    "YouTube states that if a video has more than 60 hashtags, all of the "
                    "video's hashtags are ignored. Excessive or unrelated tags can also be "
                    "treated as misleading metadata."
                ),
                suggested_action=(
                    "Keep a small number of hashtags that directly relate to the video."
                ),
                evidence=[
                    {
                        "source": "hashtags",
                        "ref_id": "HASHTAGS",
                        "detail": f"{len(hashtags)} hashtags supplied",
                        "timestamp": None,
                    }
                ],
                policy_rule_ids=rules["hashtags"],
                requires_human_review=False,
            )
        )

    # 4. Other-app watermarks in on-screen text --------------------------------
    ocr_items = [i for i in items if i.source == "ocr"]
    wm_hits = _matches(ocr_items, _WATERMARK_RE)
    if wm_hits:
        start, end = _span(wm_hits)
        findings.append(
            FindingDraft(
                source="deterministic",
                category="originality",
                finding_type="suspected_violation",
                severity="low",
                confidence="low",
                title="Possible other-app watermark or branding in frame",
                explanation=(
                    "On-screen text resembling another app's watermark was detected. Content "
                    "re-uploaded from other platforms may be treated as unoriginal, which can "
                    "affect recommendations and monetization. OCR can misread text; please "
                    "confirm visually."
                ),
                suggested_action=(
                    "Export the original, un-watermarked file. If this is someone else's "
                    "content, get permission and add substantial original commentary or editing."
                ),
                start_seconds=start,
                end_seconds=end,
                evidence=_evidence(wm_hits),
                policy_rule_ids=rules["reused"],
                requires_human_review=True,
            )
        )

    # 5. Non-speech audio: licensing cannot be verified -----------------------
    audio = extraction.get("audio") or {}
    intervals = audio.get("non_speech_sound_intervals") or []
    long_intervals = [iv for iv in intervals if iv[1] - iv[0] >= MUSIC_MIN_SECONDS]
    if long_intervals:
        total = sum(b - a for a, b in long_intervals)
        findings.append(
            FindingDraft(
                source="deterministic",
                category="licensing",
                finding_type="licensing_uncertainty",
                severity="low",
                confidence="medium",
                title=f"{total:.0f}s of non-speech audio (possible music); licence not verifiable",
                explanation=(
                    "Audio that is not speech was detected (it may be music, sound effects or "
                    "ambient sound). This system cannot identify the track or confirm you have "
                    "the rights to use it. A missing match here does NOT mean the audio is "
                    "free to use."
                ),
                suggested_action=(
                    "Confirm you own or have licensed this audio (e.g. the platform's own "
                    "licensed audio library or a licence that covers social media). Keep the "
                    "licence record."
                ),
                start_seconds=long_intervals[0][0],
                end_seconds=long_intervals[-1][1],
                evidence=[
                    {
                        "source": "audio",
                        "ref_id": f"A{i + 1}",
                        "detail": f"Non-speech sound {a:.1f}s-{b:.1f}s",
                        "timestamp": a,
                    }
                    for i, (a, b) in enumerate(long_intervals[:6])
                ],
                policy_rule_ids=rules["copyright"],
                requires_human_review=True,
            )
        )

    # 6. Checks this system cannot perform (always shown) ----------------------
    # cross_checked reviews the owner-supplied file the same way as a full upload.
    if analysis_mode not in {"full_video", "cross_checked"}:
        what = (
            "the caption and cover thumbnail"
            if analysis_mode == "caption_thumbnail"
            else "the title, description, tags and (if available) captions"
        )
        findings.append(
            FindingDraft(
                source="deterministic",
                category="community_guidelines",
                finding_type="cannot_check",
                severity="info",
                confidence="high",
                title="Video frames, speech and audio were not analysed",
                explanation=(
                    f"Only {what} were available for this review. Anything shown or said "
                    "inside the video - including music - was not checked."
                ),
                suggested_action="Upload the video file for a full analysis.",
                requires_human_review=False,
            )
        )
    findings.append(
        FindingDraft(
            source="deterministic",
            category="licensing",
            finding_type="cannot_check",
            severity="info",
            confidence="high",
            title="Platform copyright matching (Content ID, Rights Manager) was not performed",
            explanation=(
                "CreatorShield does not have access to Content ID or Meta Rights Manager "
                "reference databases. Its own checks compare the video with the catalogue "
                "indexed in this workspace and, when enabled, identify commercial music and "
                "search the web for matching frames. None of these covers every rights "
                "holder's registered work, so the absence of a copyright finding is not "
                "evidence that the video is copyright-free."
            ),
            suggested_action=(
                "Only use footage and audio you created or have documented permission/licences "
                "for. Record them in the rights ledger so they appear in the evidence pack."
            ),
            policy_rule_ids=rules["copyright"],
            requires_human_review=False,
        )
    )
    findings.append(
        FindingDraft(
            source="deterministic",
            category="disclosure",
            finding_type="cannot_check",
            severity="info",
            confidence="high",
            title="Platform disclosure settings and account standing are not visible to this tool",
            explanation=(
                "Whether you will turn on the platform's paid-promotion / paid-partnership "
                "setting, and your account's existing strikes or history, cannot be checked "
                "from the video. Platform enforcement also depends on signals this tool cannot "
                "see, so no report can guarantee protection from removal, strikes or bans."
            ),
            suggested_action="Review the platform's disclosure settings at publish time.",
            policy_rule_ids=rules["disclosure"][:1],
            requires_human_review=False,
        )
    )
    return findings
