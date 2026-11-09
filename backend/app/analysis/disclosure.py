"""Conservative disclosure signals, never an automatic compliance clearance."""

from __future__ import annotations

import re

LABEL = re.compile(
    r"(?<!\w)(?:#(?:ad|advertisement|advert|sponsored|collab|collaboration|partner|"
    r"partnership|employee|affiliate|paidpartnership|विज्ञापन|प्रायोजित)(?!\w)|"
    r"paid\s+partnership(?!\w)|sponsored(?!\w)|"
    r"(?:advertisement|advert|ad|collaboration|partnership|employee|free\s+gift|"
    # "Ad: ..." or "Ad - ...", but not a hyphenated word such as "ad-free".
    r"affiliate|विज्ञापन|प्रायोजित)(?!\w)(?=\s*[:|–—]|\s+-)|"
    r"^\s*(?:advertisement|advert|ad|collaboration|partnership|employee|free\s+gift|"
    r"affiliate|विज्ञापन|प्रायोजित)\s*$|"
    r"(?:collaboration|partnership)\s+with\s+\S+)",
    re.I,
)
# Only denial/uncertainty attached to the label; product copy elsewhere is irrelevant.
NEGATION = re.compile(
    r"(?:\b(?:not|no|never|isn't|wasn't|isnt|wasnt|without|maybe|if)|"
    r"\b(?:might|could)(?:\s+be)?)(?:\s+(?:an?|paid))?\s*$",
    re.I,
)


def disclosure_sentences(text: str) -> list[tuple[int, str]]:
    out = []
    for sentence in re.finditer(r"[^.!?\n]+", text):
        body = sentence.group()
        for match in LABEL.finditer(body):
            # A denial or uncertain assertion must never establish disclosure.
            if NEGATION.search(body[: match.start()]) or re.match(
                r"\s*(?:नहीं|नही)(?!\w)", body[match.end() :]
            ):
                continue
            out.append((sentence.start() + match.start(), body))
            break
    return out


def caption_disclosure(caption: str, sponsors: list[str] | None = None) -> bool:
    """Opening wording is a signal only; 80 chars is a review heuristic, not policy."""
    sentences = [
        (offset, text)
        for offset, text in disclosure_sentences(caption)
        if offset <= 80 and caption[:offset].count("#") < 3 and "\n" not in caption[:offset]
    ]
    names = sponsors or []
    if not names:
        return bool(sentences)
    if len(names) == 1:
        return sponsor_disclosed(caption, names, multiple=False)
    return all(
        any(
            re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, re.I) for _, text in sentences
        )
        for name in names
    )


def sponsor_disclosed(caption: str, terms: list[str], multiple: bool) -> bool:
    if not caption_disclosure(caption):
        return False
    return any(
        offset <= 80
        and caption[:offset].count("#") < 3
        and "\n" not in caption[:offset]
        and (
            any(re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", text, re.I) for t in terms)
            or (
                not multiple
                and not re.search(
                    r"sponsored\s+by|partnership\s+with|collaboration\s+with|gift\s+from",
                    text,
                    re.I,
                )
            )
        )
        for offset, text in disclosure_sentences(caption)
    )
