"""Which disclosure labels each advertising regulator treats as clear.

Regulators agree that sponsored content needs a label a viewer cannot miss, but
they disagree about the words. ASCI (India) lists "Collaboration" and
"Partnership" as permitted labels; the FTC (US) calls "collab" vague; the ASA
and CMA (UK) recommend labels that say "ad" and advise against "sponsored",
"gifted" and "affiliate" on their own. A caption that satisfies one market can
fall short in another, so labels are assessed per selected market.

The lists below paraphrase each regulator's published guidance, which is cited
through the market's rules in the policy knowledge base. They are review aids:
whether a specific post is adequately disclosed stays a human judgement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.analysis.disclosure import is_opening, iter_labels
from app.analysis.textnorm import normalise
from app.markets import MARKETS

# Labels that every supported regulator describes as clear.
UNIVERSAL_LABEL = "Ad"

# Wording some creators use as a disclosure that no supported regulator lists as clear.
_WEAK = re.compile(
    r"(?<![\w#])(?:"
    r"#(?P<sp>sp|spon|sponsor)(?!\w)|"
    r"#(?P<gifted>gifted|gift|prgift|prpackage|prhaul|prtrip|pr)(?!\w)|"
    r"(?P<gifted2>gifted\s+by)\b|"
    r"#(?P<ambassador>ambassador|brandambassador)(?!\w)|"
    r"#(?P<aff>aff|af|afflink|affiliatelink)(?!\w)|"
    r"(?P<thanks>#thanks(?!\w)|thanks\s+to\s+@?\w+)|"
    r"(?P<collaboration>collab(?=\s*[:|–—-]))|"
    r"(?P<association>in\s+association\s+with|supported\s+by|funded\s+by|"
    r"made\s+possible\s+by)\b"
    r")",
    re.IGNORECASE,
)

KIND_LABEL: dict[str, str] = {
    "ad": "Ad / Advertisement",
    "sponsored": "Sponsored",
    "paid_partnership": "Paid partnership",
    "collaboration": "Collaboration / collab",
    "partnership": "Partnership / partner",
    "brand_partnership": "Partnership with a named brand",
    "employee": "Employee",
    "free_gift": "Free gift",
    "affiliate": "Affiliate",
    "sp": "#sp / #spon",
    "gifted": "Gifted / PR",
    "gifted_by": "Gifted by a named brand",
    "ambassador": "Ambassador",
    "aff": "#aff",
    "thanks": "Thanks to a brand",
    "association": "In association with / supported by",
}

# Label kinds each regulator's guidance describes as clear.
#
# IN  ASCI: Advertisement, Ad, Sponsored, Collaboration, Partnership, Employee, Free gift;
#     the platform's own disclosure label also counts.
# US  FTC: simple terms such as "advertisement", "ad", "sponsored"; plain statements such
#     as "Gifted by [brand]"; "[Brand] partner". Not "sp", "spon", "collab", a bare
#     "gifted", or stand-alone "thanks" / "ambassador".
# UK  ASA / CMA: Ad, Advert, Advertising, Advertisement, Advertisement Feature. Advises
#     against gifted, sponsored / spon / sp, affiliate / aff, collab, "in association with",
#     "supported by" and "thanks to".
ACCEPTED: dict[str, frozenset[str]] = {
    "IN": frozenset(
        {
            "ad",
            "sponsored",
            "paid_partnership",
            "collaboration",
            "partnership",
            "brand_partnership",
            "employee",
            "free_gift",
            "affiliate",
        }
    ),
    "US": frozenset(
        {"ad", "sponsored", "paid_partnership", "brand_partnership", "free_gift", "gifted_by"}
    ),
    "UK": frozenset({"ad"}),
}


@dataclass(frozen=True)
class FoundLabel:
    text: str
    kind: str
    offset: int
    opening: bool
    denied: bool

    def clear_in(self, market: str) -> bool:
        return not self.denied and self.kind in ACCEPTED.get(market, frozenset())

    def public(self, markets: list[str]) -> dict[str, Any]:
        return {
            "text": self.text,
            "kind": self.kind,
            "kind_label": KIND_LABEL.get(self.kind, self.kind),
            "opening": self.opening,
            "denied": self.denied,
            "clear_in": [m for m in markets if self.clear_in(m)],
            "unclear_in": [m for m in markets if not self.denied and not self.clear_in(m)],
        }


def _kind(raw: str) -> str:
    text = " ".join(raw.casefold().lstrip("#").split())
    if text.startswith(("paid partnership", "paidpartnership")):
        return "paid_partnership"
    if text.startswith(("ad", "विज्ञापन")):
        return "ad"
    if text.startswith(("sponsored", "प्रायोजित")):
        return "sponsored"
    if text.startswith("collab"):
        return "collaboration"
    if text.startswith("partner"):
        return "brand_partnership" if " with " in text else "partnership"
    if text.startswith("employee"):
        return "employee"
    if text.startswith("free gift"):
        return "free_gift"
    if text.startswith("affiliate"):
        return "affiliate"
    return "ad"


def find_labels(caption: str) -> list[FoundLabel]:
    """Every disclosure-like label in the caption, clear or not, in reading order."""
    text = normalise(caption)
    found = [
        FoundLabel(raw, _kind(raw), offset, is_opening(text, offset), denied)
        for offset, raw, denied in iter_labels(text)
    ]
    taken = [(f.offset, f.offset + len(f.text)) for f in found]
    for match in _WEAK.finditer(text):
        if any(a <= match.start() < b for a, b in taken):
            continue
        kind = next(k for k, v in match.groupdict().items() if v)
        # "Gifted by Brand" names who gave it; a bare "gifted" does not.
        kind = "gifted_by" if kind == "gifted2" else kind
        found.append(
            FoundLabel(match.group(0), kind, match.start(), is_opening(text, match.start()), False)
        )
    return sorted(found, key=lambda f: f.offset)


def assess(caption: str, markets: list[str]) -> dict[str, Any]:
    """Per-market view of the caption's disclosure labels.

    status per market:
      clear    an accepted label sits in the opening of the caption
      buried   an accepted label exists, but not in the opening
      unclear  only labels that this market's regulator does not treat as clear
      none     no label at all
    """
    labels = find_labels(caption)
    asserted = [f for f in labels if not f.denied]
    by_market: dict[str, dict[str, Any]] = {}
    for market in markets:
        clear = [f for f in asserted if f.clear_in(market)]
        if any(f.opening for f in clear):
            status = "clear"
        elif clear:
            status = "buried"
        elif asserted:
            status = "unclear"
        else:
            status = "none"
        by_market[market] = {
            "status": status,
            "regulator": MARKETS[market].regulator,
            "clear_labels": [f.text for f in clear],
            "unclear_labels": [f.text for f in asserted if not f.clear_in(market)],
        }
    return {"labels": [f.public(markets) for f in labels], "by_market": by_market}
