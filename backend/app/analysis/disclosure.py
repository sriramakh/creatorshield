"""Conservative disclosure signals, never an automatic compliance clearance.

A label only counts when it is asserted: denials ("not sponsored",
"non-sponsored", "nobody sponsored this"), uncertainty ("maybe sponsored") and
questions ("Is this sponsored? No ...") never establish disclosure. Input is
normalised first (NFKC, zero-width characters removed, typographic quotes made
ASCII) so "#ａｄ" or "ad​:" read as "#ad" / "ad:".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.analysis.textnorm import normalise

_WORDS = (
    r"advertisement(?:\s+feature)?|advertising|advert|ad|collaboration|partnership|employee|"
    r"free\s+gift|affiliate|विज्ञापन|प्रायोजित"
)
# Pictographs, dingbats and the emoji variation selector.
_EMOJI = "[\U0001f000-\U0001faff☀-➿⬀-⯿️]"
# "Collaboration with my mom" is ordinary prose; "Collaboration with Brand" is a label.
_NOT_PERSONAL = (
    r"(?!(?:my|our|your|his|her|their|the|a|an|this|that|these|those|some|me|us|him|"
    r"them|you|friends?|family|mom|mum|mother|dad|father|parents?|wife|husband|"
    r"sister|brother|kids?|children|team|class|classmates?|neighbou?rs?)\b)"
)

LABEL = re.compile(
    r"(?<!\w)(?:#(?:ad|advertisement|advertisementfeature|advertising|advert|sponsored|"
    r"collab|collaboration|partner|"
    r"partnership|employee|affiliate|paidpartnership|विज्ञापन|प्रायोजित)(?!\w)|"
    r"paid\s+partnership(?!\w)|sponsored(?!\w)|"
    # "Ad: ..." or "Ad - ...", but not a hyphenated word such as "ad-free".
    rf"(?:{_WORDS})(?!\w)(?=\s*[:|–—]|\s+-)|"
    # A sentence that opens with the bare word and an emoji: "Ad 📢 Brand".
    rf"^\s*(?:{_EMOJI}\s*)*(?:{_WORDS})(?!\w)(?=\s*{_EMOJI})|"
    rf"^\s*(?:{_EMOJI}\s*)*(?:{_WORDS})\s*(?:{_EMOJI}\s*)*$|"
    rf"(?:collaboration|partnership)\s+with\s+{_NOT_PERSONAL}\S+)",
    re.I,
)

_NEG_WORDS = (
    r"not|no|never|isn't|wasn't|aren't|weren't|ain't|isnt|wasnt|arent|werent|"
    r"without|maybe|perhaps|if|whether"
)
# Words that may sit between a denial and the label: "not even sponsored".
_FILLER = (
    r"(?:even|really|actually|ever|been|being|currently|officially|technically|"
    r"exactly|yet|at\s+all|in\s+any\s+way|an?|paid)"
)
# Only denial/uncertainty attached to the label; product copy elsewhere is irrelevant.
NEGATION = re.compile(
    rf"(?:\b(?:{_NEG_WORDS})|\b(?:might|could|may)(?:\s+be)?|"
    r"\b(?:nobody|no[\s-]one|nothing|none|no\s+(?:brand|company|companies|one))"
    r"(?:\s+[^\s,;:|]+){0,3}?)"
    rf"(?:\s+{_FILLER})*\s*$"
    r"|\bnon[\s-]?$|\bun-$",
    re.I,
)
# The rest of the sentence is only a retraction: "Sponsored - not really".
_POST_NEGATION = re.compile(
    r"\s*[-–—,(:]*\s*(?:not(?:\s+really|\s+at\s+all)?|nope|nah|jk|just\s+kidding|lol\s+no)"
    r"\s*[)!.]*\s*$",
    re.I,
)
_HINDI_DENIAL = re.compile(r"\s*(?:नहीं|नही)(?!\w)")
_QUESTION_START = re.compile(
    r"^\s*(?:(?:so|wait|but|and|ok|okay)\s*,?\s+)?(?:is|was|are|were|am|do|does|did|who|what|"
    r"why|how|can|could|would|should|will|isn't|wasn't|whether)\b",
    re.I,
)
_TRAILING_NOISE = re.compile(rf"(?:\s|{_EMOJI}|[\"')\]])*$")
_CLAUSE_BREAK = re.compile(r"[,;|]|\s(?:but|and|or)\s", re.I)
_SPONSOR_WORDING = re.compile(
    r"sponsored\s+by|partnership\s+with|collaboration\s+with|gift\s+from", re.I
)

# Opening-caption heuristic: a review aid, not a platform rule.
OPENING_CHARS = 80
MAX_HASHTAGS_BEFORE = 3


@dataclass
class LabelledSentence:
    """A sentence that asserts at least one disclosure label."""

    offset: int  # offset of the first accepted label in the normalised text
    text: str
    # Spans (relative to ``text``) of clauses whose label was denied.
    negated: list[tuple[int, int]] = field(default_factory=list)


# Denials are read from a bounded window before the label. Keeping it bounded
# keeps the scan linear on long, label-heavy text.
_WINDOW = 120


def _clause(body: str, start: int, end: int) -> tuple[int, int]:
    """Span of the clause around a label (between commas, semicolons, 'but' ...)."""
    left = 0
    for m in _CLAUSE_BREAK.finditer(body, max(0, start - _WINDOW), start):
        left = m.end()
    right_match = _CLAUSE_BREAK.search(body, end)
    return left, right_match.start() if right_match else len(body)


def _prefix(body: str, start: int) -> str:
    """Up to _WINDOW characters before ``start``, cut at a word boundary."""
    if start <= _WINDOW:
        return body[:start]
    window = body[start - _WINDOW : start]
    cut = window.find(" ")
    return window[cut + 1 :] if cut >= 0 else window


def _is_question(text: str, sentence: re.Match[str], body: str, label_end: int) -> bool:
    terminator = text[sentence.end() : sentence.end() + 1]
    if terminator != "?":
        return False
    return bool(_TRAILING_NOISE.fullmatch(body, label_end)) or bool(_QUESTION_START.match(body))


def _denied(text: str, sentence: re.Match[str], body: str, match: re.Match[str]) -> bool:
    """The label is denied, uncertain or asked as a question rather than asserted."""
    return bool(
        NEGATION.search(_prefix(body, match.start()))
        or _HINDI_DENIAL.match(body, match.end())
        or _POST_NEGATION.fullmatch(body, match.end())
        or _is_question(text, sentence, body, match.end())
    )


def iter_labels(text: str) -> list[tuple[int, str, bool]]:
    """(offset, label text, denied) for every label in already-normalised ``text``."""
    out: list[tuple[int, str, bool]] = []
    for sentence in re.finditer(r"[^.!?\n]+", text):
        body = sentence.group()
        for match in LABEL.finditer(body):
            out.append(
                (
                    sentence.start() + match.start(),
                    match.group(0),
                    _denied(text, sentence, body, match),
                )
            )
    return out


def is_opening(text: str, offset: int) -> bool:
    """``offset`` sits in the part of the caption a viewer sees without expanding it."""
    return _is_opening(text, offset)


def _scan(text: str) -> list[LabelledSentence]:
    """Sentences of already-normalised ``text`` that assert a label."""
    out: list[LabelledSentence] = []
    for sentence in re.finditer(r"[^.!?\n]+", text):
        body = sentence.group()
        accepted: int | None = None
        negated: list[tuple[int, int]] = []
        for match in LABEL.finditer(body):
            if _denied(text, sentence, body, match):
                negated.append(_clause(body, match.start(), match.end()))
            elif accepted is None:
                accepted = match.start()
        if accepted is not None:
            out.append(LabelledSentence(sentence.start() + accepted, body, negated))
    return out


def disclosure_sentences(text: str) -> list[tuple[int, str]]:
    """(offset, sentence) for each sentence that asserts a disclosure label."""
    return [(s.offset, s.text) for s in _scan(normalise(text))]


def _is_opening(text: str, offset: int) -> bool:
    before = text[:offset]
    return (
        offset <= OPENING_CHARS and before.count("#") < MAX_HASHTAGS_BEFORE and "\n" not in before
    )


def _named(sentence: LabelledSentence, name: str) -> bool:
    """The sponsor is named in the sentence outside every denied clause."""
    pattern = re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)", re.I)
    return any(
        not any(a <= m.start() < b for a, b in sentence.negated)
        for m in pattern.finditer(sentence.text)
    )


def _clean_names(names: list[str] | None) -> list[str]:
    return [n for n in (normalise(x).strip() for x in names or []) if n]


def caption_disclosure(caption: str, sponsors: list[str] | None = None) -> bool:
    """Opening wording is a signal only; 80 chars is a review heuristic, not policy."""
    names = _clean_names(sponsors)
    if len(names) == 1:
        return sponsor_disclosed(caption, names, multiple=False)
    text = normalise(caption)
    opening = [s for s in _scan(text) if _is_opening(text, s.offset)]
    if not names:
        return bool(opening)
    return all(any(_named(s, name) for s in opening) for name in names)


def sponsor_disclosed(caption: str, terms: list[str], multiple: bool) -> bool:
    """One sponsor (matched by any of ``terms``) has an opening-caption disclosure.

    With a single sponsor, a generic label ("#ad") that names no other sponsor
    is accepted. With several sponsors, the sponsor must be named next to a label.
    """
    text = normalise(caption)
    names = _clean_names(terms)
    for sentence in _scan(text):
        if not _is_opening(text, sentence.offset):
            continue
        if any(_named(sentence, name) for name in names):
            return True
        if not multiple and not _SPONSOR_WORDING.search(sentence.text):
            return True
    return False
