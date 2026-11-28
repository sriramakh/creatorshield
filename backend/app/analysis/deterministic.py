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

from app import markets as market_registry
from app.analysis import market_disclosure
from app.analysis.community_guidelines import is_finance_claim, run_community_guideline_checks
from app.analysis.disclosure import caption_disclosure, disclosure_sentences
from app.analysis.textnorm import normalise
from app.platforms import PLATFORMS
from app.schemas import FindingDraft

TIKTOK_RULES: dict[str, list[str]] = {
    "disclosure": [],
    "copyright": [],
    "hashtags": [],
    "health_claims": [],
    "reused": [],
    "overview": [],
}
US_RULES: dict[str, list[str]] = {
    "disclosure": ["US-FTC-DISCLOSURES-101", "US-FTC-FAQ-HOW", "US-FTC-GUIDES-255"],
    "health_claims": ["US-FTC-HEALTH-CLAIMS", "US-FTC-GUIDES-255-TYPICALITY"],
}
UK_RULES: dict[str, list[str]] = {
    "disclosure": ["UK-ASA-INFLUENCER-GUIDE", "UK-CMA-HIDDEN-ADS", "UK-CAP-CODE-S2"],
    "health_claims": [],
}

# Rule IDs each check cites, by platform family. Every ID must exist in the policy
# knowledge base for that family (enforced by tests).
FAMILY_RULES: dict[str, dict[str, list[str]]] = {
    "youtube": {
        "disclosure": ["YT-DISC-PAID-PROMO"],
        "copyright": ["YT-COPY-BASICS"],
        "hashtags": ["YT-HASHTAGS"],
        "health_claims": ["YT-MON-AD-FRIENDLY", "YT-CG-MEDMISINFO"],
        "reused": ["YT-MON-YPP"],
        "overview": ["YT-CG-OVERVIEW"],
    },
    "instagram": {
        "disclosure": ["IG-PAID-PARTNERSHIP", "IG-BRANDED-DISCLOSURE"],
        "copyright": ["IG-COPYRIGHT"],
        "hashtags": [],
        "health_claims": ["IG-MON-CONTENT", "IG-RECOMMENDATIONS"],
        "reused": ["IG-MON-CONTENT", "IG-RECOMMENDATIONS"],
        "overview": ["META-CS-OVERVIEW"],
    },
    "tiktok": TIKTOK_RULES,
}

# Rule IDs each audience market adds to the disclosure and claims checks.
MARKET_RULES: dict[str, dict[str, list[str]]] = {
    "IN": {
        "disclosure": ["IN-ASCI-INFLUENCER", "IN-CCPA-ENDORSE"],
        "health_claims": ["IN-ASCI-INFLUENCER"],
    },
    "US": US_RULES,
    "UK": UK_RULES,
}

# What each regulator expects of a disclosure, in one sentence, for suggested actions.
MARKET_ADVICE: dict[str, str] = {
    "IN": (
        "ASCI (India) expects a permitted label such as Advertisement, Ad, Sponsored, "
        "Collaboration or Partnership up front, where it cannot be missed."
    ),
    "US": (
        "The FTC (US) expects a simple, clear disclosure such as 'Ad' or 'Sponsored' placed "
        "with the endorsement itself, in the video as well as the caption, and not buried "
        "among hashtags."
    ),
    "UK": (
        "The ASA and CMA (UK) expect an upfront label that says it is advertising, such as "
        "'Ad' or 'Advert', and advise against 'sponsored', 'gifted', 'collab' and 'affiliate' "
        "on their own."
    ),
}


def rules_for(platform: str, markets: list[str]) -> dict[str, list[str]]:
    """Rule IDs per check for a target platform and its audience markets."""
    rules = {k: list(v) for k, v in FAMILY_RULES[PLATFORMS[platform].family].items()}
    for market in markets:
        for key, ids in MARKET_RULES.get(market, {}).items():
            rules[key] = [*rules.get(key, []), *[i for i in ids if i not in rules.get(key, [])]]
    return rules


# Promotion signals (English, Hindi, and common Hinglish transliterations).
_PROMO_PATTERNS = [
    r"\b(?:use|apply)\s+(?:my\s+)?(?:promo\s+|discount\s+|coupon\s+)?code\b"
    r"(?!\s+(?:to|for|in|from|that|which|snippets?|blocks?|examples?|editors?)\b)",
    # "code GLOW20" / "code SAVE": the token must look like a code (contains a
    # digit, or is written in capitals), so "the code for this function" or
    # "error code" lines are not promotions. The token part is case-sensitive.
    r"(?<!error )(?<!status )(?<!zip )(?<!pin )(?<!area )(?<!source )\bcode\s+"
    r"(?-i:(?=[A-Za-z0-9]{3,}\b)(?:[A-Za-z]*\d[A-Za-z0-9]*|[A-Z]{3,}[A-Z0-9]*))\b",
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
# Food sense of "cured" (cured ham, salt-cured salmon) is not a health claim.
_CURE = (
    r"(?<!salt-)(?<!salt )\bcure[sd]?\b(?!\s+(?:ham|meats?|salmon|bacon|pork|sausages?|"
    r"salami|beef|fish|duck|eggs?|yolks?|lemons?|olives?|tobacco|concrete|resin)\b)"
)
# A guarantee is a claim when it is about results, health or the body.
# "I guarantee you will laugh" is not.
_GUARANTEE = (
    r"\bguarantee[sd]?\b(?=.{0,50}?\b(?:results?|cure[sd]?|heal(?:s|ed|ing)?|lose|loss|"
    r"weight|fat|kgs?|pounds|lbs|skin|hair|acne|pimples?|glow|fair(?:er|ness)?|whiten\w*|"
    r"growth|grow|effective|relief|pain|diabetes|cancer|sugar|bp|immunity|inches|"
    r"muscles?|abs|height|works?|fix(?:es|ed)?)\b)"
    r"|\bguaranteed\s+(?:results?|cure|weight\s+loss|fat\s+loss|relief|growth)\b"
)
_HEALTH_CLAIM_PATTERNS = [
    _CURE,
    _GUARANTEE,
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


def thumbnail_frame_ids(extraction: dict[str, Any]) -> set[str]:
    """Frames that are a post's cover image, not a moment in the video."""
    return {f["id"] for f in extraction.get("frames") or [] if f.get("reason") == "thumbnail"}


def collect_text_items(
    caption: str, hashtags: list[str], extraction: dict[str, Any]
) -> list[TextItem]:
    """Text to check, normalised (NFKC, invisible characters, ASCII quotes)."""
    items: list[TextItem] = []
    if caption.strip():
        items.append(TextItem("caption", "CAPTION", normalise(caption), None, None))
    if hashtags:
        tags = normalise(" ".join(f"#{h}" for h in hashtags))
        items.append(TextItem("hashtags", "HASHTAGS", tags, None, None))
    for seg in (extraction.get("transcript") or {}).get("segments", []):
        items.append(
            TextItem("transcript", seg["id"], normalise(seg["text"]), seg["start"], seg["end"])
        )
    thumbnails = thumbnail_frame_ids(extraction)
    for o in extraction.get("ocr") or []:
        # Text on a cover thumbnail has no position in the video.
        ts = None if o.get("frame_id") in thumbnails else o.get("timestamp")
        items.append(TextItem("ocr", o["id"], normalise(o["text"]), ts, ts))
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
    sponsorship: dict[str, Any] | None = None,
    markets: list[str] | None = None,
) -> list[FindingDraft]:
    markets = market_registry.clean(markets)
    family = PLATFORMS[platform].family
    rules = rules_for(platform, markets)
    items = collect_text_items(caption, hashtags, extraction)
    findings: list[FindingDraft] = []

    # 1. Promotion signals without a visible disclosure ------------------------
    promo_hits = _matches(items, _PROMO_RE)
    context = sponsorship or {}
    sponsors = context.get("sponsors", [])
    declared = context.get("relationship", "unknown") not in {"unknown", "none"}
    disclosed = caption_disclosure(caption, sponsors)
    if (promo_hits or declared) and not disclosed:
        start, end = _span(promo_hits)
        label = PLATFORMS[platform].disclosure_setting
        weak = [
            f.text
            for f in market_disclosure.find_labels(caption)
            if not f.denied and not any(f.clear_in(m) for m in markets)
        ]
        weak_note = (
            f" The caption uses {_quote_list(weak)}, which "
            f"{_join_words([market_registry.MARKETS[m].regulator for m in markets])} "
            "guidance does not treat as a clear disclosure."
            if weak
            else ""
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
                    "codes or offers), or a commercial relationship was declared. "
                    "No sufficiently associated opening-caption disclosure such as "
                    "#ad or 'sponsored' was detected. Video or spoken wording alone "
                    "does not resolve this check. If you received payment, "
                    "free products, commission or any other benefit, the platform expects this "
                    "to be disclosed. This check cannot tell whether a commercial relationship "
                    "actually exists." + weak_note
                ),
                suggested_action=(
                    f"If this is a paid, gifted or affiliate promotion, enable {label} when "
                    "publishing and add a clear disclosure (e.g. 'Ad') at the start of the "
                    "caption and on screen. " + " ".join(MARKET_ADVICE[m] for m in markets)
                ),
                start_seconds=start,
                end_seconds=end,
                evidence=_evidence(promo_hits),
                policy_rule_ids=rules["disclosure"],
                requires_human_review=True,
            )
        )

    if promo_hits or declared or any(disclosure_sentences(i.text) for i in items):
        findings.append(
            FindingDraft(
                source="deterministic",
                category="disclosure",
                finding_type="cannot_check",
                severity="info",
                confidence="high",
                title="Disclosure adequacy needs human review",
                explanation=(
                    "Disclosure wording detected in the opening caption. "
                    if disclosed
                    else "Opening disclosure is missing, ambiguous or not linked to every sponsor. "
                )
                + "Caption position is a heuristic, not a platform visibility measurement. "
                "Sampled frames cannot establish label duration, readability or prominence. "
                "Relationship: " + context.get("relationship", "unknown") + ". "
                "Sponsors: " + (", ".join(sponsors) or "not supplied") + ".",
                suggested_action="Review each sponsor's disclosure in the final caption and video. "
                "Verify on-screen timing and readability, and confirm the platform "
                "paid-promotion setting at publishing. That setting was not verified.",
                policy_rule_ids=rules["disclosure"],
                requires_human_review=True,
            )
        )

    # 1b. A label that is clear in one market can be unclear in another ---------
    if disclosed:
        findings.extend(_market_label_findings(caption, markets, rules["disclosure"]))

    # 2. Strong efficacy / guarantee claims ----------------------------------
    # A finance "guaranteed returns" line is a community-guideline scam flag, not a
    # medical-cure claim. Leave it to that check when "guarantee" is the only hit.
    health_hits = [
        hit
        for hit in _matches([i for i in items if i.source != "hashtags"], _HEALTH_RE)
        if not _finance_guarantee_only(hit)
    ]
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

    findings.extend(run_community_guideline_checks(platform, items))

    # 3. YouTube hashtag limit -------------------------------------------------
    if family == "youtube" and len(hashtags) > YOUTUBE_HASHTAG_LIMIT:
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
    # TikTok's own watermark is not "another app" on a TikTok post.
    watermarks = _WATERMARK_RE[1:] if family == "tiktok" else _WATERMARK_RE
    wm_hits = _matches(ocr_items, watermarks)
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
        what = {
            "caption_thumbnail": "the caption and cover thumbnail",
            "caption_only": "the caption and hashtags",
        }.get(analysis_mode, "the title, description, tags and (if available) captions")
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
                    "inside the video - including music, nudity, violence and other "
                    "visual-only risks - was not checked."
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
    if analysis_mode in {"full_video", "cross_checked"}:
        findings.append(
            FindingDraft(
                source="deterministic",
                category="community_guidelines",
                finding_type="cannot_check",
                severity="info",
                confidence="high",
                title="Imagery was not classified for community-guideline risks",
                explanation=(
                    "The community-guideline check reads the transcript, on-screen text, "
                    "caption and hashtags. It does not classify frames, so nudity, graphic "
                    "violence, weapons and other visual-only risks are missed unless words "
                    "mention them. When an AI review runs, it sees sampled frames only, and "
                    "brief moments between samples can still be missed."
                ),
                suggested_action=(
                    "Watch the cut yourself for anything the words do not mention. "
                    "Do not treat a clear wording check as a clearance of the picture."
                ),
                policy_rule_ids=rules["overview"],
                requires_human_review=False,
            )
        )
    return findings


def has_promo_signals(caption: str, hashtags: list[str], extraction: dict[str, Any]) -> bool:
    """Promotion wording (codes, discounts, 'link in bio') anywhere in the content."""
    return bool(_matches(collect_text_items(caption, hashtags, extraction), _PROMO_RE))


def _join_words(values: list[str]) -> str:
    if len(values) <= 1:
        return "".join(values)
    return ", ".join(values[:-1]) + " and " + values[-1]


def _quote_list(values: list[str]) -> str:
    return _join_words([f'"{v}"' for v in dict.fromkeys(values)])


def _market_label_findings(
    caption: str, markets: list[str], disclosure_rules: list[str]
) -> list[FindingDraft]:
    """One finding when the caption's label is clear in some selected markets but not all."""
    assessment = market_disclosure.assess(caption, markets)["by_market"]
    short = [m for m in markets if assessment[m]["status"] not in {"clear", "none"}]
    if not short:
        return []
    unclear = [x for m in short for x in assessment[m]["unclear_labels"]]
    buried = [m for m in short if assessment[m]["status"] == "buried"]
    regulators = _join_words([market_registry.MARKETS[m].regulator for m in short])
    where = market_registry.names(short)
    market_rules = {r for m in short for r in MARKET_RULES[m].get("disclosure", [])}
    if unclear:
        explanation = (
            f"The caption discloses with {_quote_list(unclear)}. {regulators} guidance does "
            f"not treat that wording as a clear disclosure, so viewers in {where} may not "
            "recognise the post as advertising. Regulators differ on which labels they accept; "
            "a label that works in one market can fall short in another."
        )
    else:
        explanation = (
            f"A clear label is in the caption but not at the start, where {regulators} "
            f"guidance expects it for viewers in {where}. A label after a line break, after "
            "several hashtags or behind 'more' is easy to miss."
        )
    return [
        FindingDraft(
            source="deterministic",
            category="disclosure",
            finding_type="suspected_violation",
            severity="medium",
            confidence="medium",
            title=(
                f"Disclosure label may not be clear enough for {where}"
                if unclear or not buried
                else f"Disclosure is not at the start of the caption for {where}"
            ),
            explanation=explanation,
            suggested_action=(
                "Open the caption with 'Ad', which every selected market's guidance treats "
                "as clear. " + " ".join(MARKET_ADVICE[m] for m in short)
            ),
            evidence=[
                {
                    "source": "caption",
                    "ref_id": "CAPTION",
                    "detail": f"Label used: {_quote_list(unclear)}"
                    if unclear
                    else "Label is not in the opening of the caption",
                    "timestamp": None,
                }
            ],
            policy_rule_ids=[r for r in disclosure_rules if r in market_rules],
            requires_human_review=True,
        )
    ]


def _finance_guarantee_only(hit: tuple[TextItem, str]) -> bool:
    item, match = hit
    if not re.fullmatch(r"guarantee[sd]?", match, re.IGNORECASE):
        return False
    if not is_finance_claim(item.text):
        return False
    return not any(pat.search(item.text) for pat in _HEALTH_RE if pat.pattern != _GUARANTEE)
