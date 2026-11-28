"""Brand-brief checks: does the content do what the brand asked for?

A brief is the creator's or agency's own record of what a sponsor requires:
lines that must be said, wording that must not be used, hashtags and handles
that must appear, competitors that must not be named. These checks compare the
brief with the caption, hashtags, speech and on-screen text.

They are contract checks, not policy checks. Findings carry no policy rule and
are not counted in the policy risk indicator; they feed the publish-readiness
checklist instead. Speech recognition and OCR miss words, so a "not found"
result for something that should be in the video always asks for a human look.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.analysis.disclosure import OPENING_CHARS
from app.analysis.textnorm import normalise
from app.schemas import FindingDraft

MAX_ITEMS = 20
MAX_ITEM_CHARS = 200

BriefKind = Literal[
    "must_say",
    "must_not_say",
    "required_hashtag",
    "required_mention",
    "competitor",
    "required_disclosure",
]
BriefStatus = Literal["met", "missing", "violated", "unverified"]

# Modes where speech and on-screen text were read from the video itself.
_VIDEO_MODES = {"full_video", "cross_checked"}


def _clean_list(values: list[str], strip_chars: str = "") -> list[str]:
    out: list[str] = []
    for raw in values:
        value = " ".join(normalise(raw).split()).strip()
        if strip_chars:
            value = value.lstrip(strip_chars).strip()
        if not value:
            continue
        if len(value) > MAX_ITEM_CHARS:
            raise ValueError(f"Brief entries must be at most {MAX_ITEM_CHARS} characters")
        if value.casefold() not in {v.casefold() for v in out}:
            out.append(value)
    if len(out) > MAX_ITEMS:
        raise ValueError(f"A brief list can hold at most {MAX_ITEMS} entries")
    return out


class BriefSpec(BaseModel):
    """What a sponsor's brief requires. Stored with the review as untrusted user input."""

    name: str = Field(default="", max_length=120)
    brand: str = Field(default="", max_length=120)
    must_say: list[str] = Field(default_factory=list)
    must_not_say: list[str] = Field(default_factory=list)
    required_hashtags: list[str] = Field(default_factory=list)
    required_mentions: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    required_disclosure: str | None = Field(default=None, max_length=80)
    notes: str = Field(default="", max_length=2000)

    @field_validator("name", "brand", "notes")
    @classmethod
    def _strip(cls, value: str) -> str:
        return normalise(value).strip()

    @field_validator("must_say", "must_not_say", "competitors")
    @classmethod
    def _phrases(cls, values: list[str]) -> list[str]:
        return _clean_list(values)

    @field_validator("required_hashtags")
    @classmethod
    def _hashtags(cls, values: list[str]) -> list[str]:
        return _clean_list(values, "#")

    @field_validator("required_mentions")
    @classmethod
    def _mentions(cls, values: list[str]) -> list[str]:
        return _clean_list(values, "@")

    @field_validator("required_disclosure")
    @classmethod
    def _disclosure(cls, value: str | None) -> str | None:
        value = " ".join(normalise(value or "").split()).strip()
        return value or None

    def is_empty(self) -> bool:
        return not (
            self.must_say
            or self.must_not_say
            or self.required_hashtags
            or self.required_mentions
            or self.competitors
            or self.required_disclosure
        )


@dataclass(frozen=True)
class _Text:
    source: str  # caption | hashtags | transcript | ocr
    ref_id: str
    text: str
    timestamp: float | None
    # Two neighbouring transcript segments joined, to catch a line split between them.
    joined: bool = False


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Match the words of ``phrase`` in order, ignoring case and punctuation between them."""
    tokens = re.findall(r"\w+", normalise(phrase), re.UNICODE)
    if not tokens:
        return re.compile(r"(?!)")
    body = r"\W+".join(re.escape(t) for t in tokens)
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)


def _texts(caption: str, hashtags: list[str], extraction: dict[str, Any]) -> list[_Text]:
    out: list[_Text] = []
    if caption.strip():
        out.append(_Text("caption", "CAPTION", normalise(caption), None))
    if hashtags:
        out.append(_Text("hashtags", "HASHTAGS", " ".join(f"#{h}" for h in hashtags), None))
    segments = (extraction.get("transcript") or {}).get("segments", [])
    for seg in segments:
        out.append(_Text("transcript", seg["id"], normalise(seg["text"]), seg.get("start")))
    # A required line is often split across two transcript segments.
    for first, second in zip(segments, segments[1:], strict=False):
        joined = normalise(f"{first['text']} {second['text']}")
        out.append(_Text("transcript", first["id"], joined, first.get("start"), joined=True))
    for item in extraction.get("ocr") or []:
        out.append(_Text("ocr", item["id"], normalise(item["text"]), item.get("timestamp")))
    return out


def _find(pattern: re.Pattern[str], texts: list[_Text], limit: int = 4) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    # Joined segment pairs are a fallback: only used when no single segment has the phrase.
    in_one_segment = any(
        t.source == "transcript" and not t.joined and pattern.search(t.text) for t in texts
    )
    for item in texts:
        if item.joined and in_one_segment:
            continue
        match = pattern.search(item.text)
        if not match or (item.source, item.ref_id) in seen:
            continue
        seen.add((item.source, item.ref_id))
        start = max(0, match.start() - 40)
        hits.append(
            {
                "source": item.source,
                "ref_id": item.ref_id,
                "detail": f'"{match.group(0)}" in: {item.text[start : start + 160]}',
                "timestamp": item.timestamp,
            }
        )
        if len(hits) >= limit:
            break
    return hits


def _tag_set(caption: str, hashtags: list[str]) -> set[str]:
    tags = {normalise(h).lstrip("#").casefold() for h in hashtags}
    tags |= {m.casefold() for m in re.findall(r"#(\w+)", normalise(caption), re.UNICODE)}
    return tags


def _where(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: h[k] for k in ("source", "ref_id", "timestamp")} for h in hits]


def _quoted(values: list[str]) -> str:
    return ", ".join(f'"{v}"' for v in values)


def _span(evidence: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    times = [e["timestamp"] for e in evidence if e.get("timestamp") is not None]
    return (min(times), max(times)) if times else (None, None)


def run_brief_checks(
    brief: BriefSpec,
    caption: str,
    hashtags: list[str],
    extraction: dict[str, Any],
    analysis_mode: str = "full_video",
) -> tuple[dict[str, Any], list[FindingDraft]]:
    """Compare content with a brief. Returns (summary for the checklist, findings)."""
    texts = _texts(caption, hashtags, extraction)
    video_read = analysis_mode in _VIDEO_MODES
    brand = brief.brand or brief.name or "the brand"
    items: list[dict[str, Any]] = []
    findings: list[FindingDraft] = []

    def record(kind: BriefKind, text: str, status: BriefStatus, hits: list[dict[str, Any]]) -> None:
        items.append({"kind": kind, "text": text, "status": status, "where": _where(hits)})

    def finding(
        title: str,
        explanation: str,
        action: str,
        severity: Literal["low", "medium", "high"],
        confidence: Literal["low", "medium", "high"],
        evidence: list[dict[str, Any]],
        review: bool,
    ) -> None:
        start, end = _span(evidence)
        findings.append(
            FindingDraft(
                source="deterministic",
                category="brand_brief",
                finding_type="observed_evidence",
                severity=severity,
                confidence=confidence,
                title=title,
                explanation=explanation,
                suggested_action=action,
                start_seconds=start,
                end_seconds=end,
                evidence=evidence[:6],
                policy_rule_ids=[],
                requires_human_review=review,
            )
        )

    # ---- lines that must appear ---------------------------------------------
    missing: list[str] = []
    for phrase in brief.must_say:
        hits = _find(_phrase_pattern(phrase), texts)
        if hits:
            record("must_say", phrase, "met", hits)
        elif video_read:
            record("must_say", phrase, "missing", [])
            missing.append(phrase)
        else:
            record("must_say", phrase, "unverified", [])
    if missing:
        finding(
            f"Brand brief: {len(missing)} required "
            f"{'line was' if len(missing) == 1 else 'lines were'} not found",
            f"The brief for {brand} asks for wording that was not found in the caption, "
            f"speech or on-screen text: {_quoted(missing)}. Speech recognition and on-screen "
            "text reading can miss or misspell words, so confirm by watching the cut.",
            "Add the required wording, or confirm it is in the video and record why this "
            "check missed it.",
            "medium",
            "medium",
            [],
            True,
        )

    # ---- wording that must not appear ---------------------------------------
    for kind, phrases, noun in (
        ("must_not_say", brief.must_not_say, "restricted wording"),
        ("competitor", brief.competitors, "a competitor"),
    ):
        violated: list[str] = []
        evidence: list[dict[str, Any]] = []
        for phrase in phrases:
            hits = _find(_phrase_pattern(phrase), texts)
            if hits:
                record(kind, phrase, "violated", hits)  # type: ignore[arg-type]
                violated.append(phrase)
                evidence.extend(hits)
            else:
                record(kind, phrase, "met" if video_read else "unverified", [])  # type: ignore[arg-type]
        if violated:
            finding(
                f"Brand brief: {noun} appears ({_quoted(violated[:3])}"
                + (", ..." if len(violated) > 3 else "")
                + ")",
                f"The brief for {brand} says this must not appear: {_quoted(violated)}.",
                "Remove or replace this wording before sending the content for approval.",
                "high",
                "high"
                if all(e["source"] in {"caption", "hashtags"} for e in evidence)
                else "medium",
                evidence,
                not all(e["source"] in {"caption", "hashtags"} for e in evidence),
            )

    # ---- hashtags and handles ------------------------------------------------
    tags = _tag_set(caption, hashtags)
    missing_tags = []
    for tag in brief.required_hashtags:
        if tag.casefold() in tags:
            record("required_hashtag", f"#{tag}", "met", [])
        else:
            record("required_hashtag", f"#{tag}", "missing", [])
            missing_tags.append(f"#{tag}")
    if missing_tags:
        finding(
            "Brand brief: required hashtags are missing",
            f"The brief for {brand} requires {', '.join(missing_tags)}, which "
            "are not in the caption or hashtags.",
            "Add the required hashtags to the caption.",
            "medium",
            "high",
            [],
            False,
        )

    caption_only = [t for t in texts if t.source in {"caption", "hashtags"}]
    missing_mentions = []
    for handle in brief.required_mentions:
        pattern = re.compile(rf"(?<![\w@])@{re.escape(handle)}(?![\w.])", re.IGNORECASE)
        hits = _find(pattern, caption_only)
        if hits:
            record("required_mention", f"@{handle}", "met", hits)
        else:
            record("required_mention", f"@{handle}", "missing", [])
            missing_mentions.append(f"@{handle}")
    if missing_mentions:
        finding(
            "Brand brief: required account mentions are missing",
            f"The brief for {brand} requires the caption to mention {', '.join(missing_mentions)}.",
            "Add the required @mentions to the caption. Tagging the account in the "
            "platform's own tag field was not checked.",
            "medium",
            "high",
            [],
            False,
        )

    # ---- the exact disclosure label the brand asked for ----------------------
    if brief.required_disclosure:
        label = brief.required_disclosure
        pattern = (
            re.compile(rf"(?<![\w#]){re.escape(label)}(?!\w)", re.IGNORECASE)
            if label.startswith("#")
            else _phrase_pattern(label)
        )
        text = normalise(caption)
        match = pattern.search(text)
        if match and match.start() <= OPENING_CHARS:
            record("required_disclosure", label, "met", [])
        else:
            record("required_disclosure", label, "missing", [])
            where = "is not in the caption" if not match else "is not at the start of the caption"
            finding(
                f'Brand brief: the required disclosure "{label}" {where}',
                f'The brief for {brand} requires the disclosure "{label}". It {where}. '
                "A label the brand requires does not replace what the platform or your "
                "advertising regulator expects; both apply.",
                f'Put "{label}" at the start of the caption.',
                "medium",
                "high",
                [],
                False,
            )

    met = sum(1 for i in items if i["status"] == "met")
    summary = {
        "brand": brief.brand,
        "name": brief.name,
        "scope": "video" if video_read else "caption_only",
        "items": items,
        "met": met,
        "total": len(items),
        "failed": sum(1 for i in items if i["status"] in {"missing", "violated"}),
        "unverified": sum(1 for i in items if i["status"] == "unverified"),
    }
    return summary, findings
