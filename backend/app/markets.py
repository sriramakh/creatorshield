"""Audience markets: whose advertising guidance applies to a post.

Platform policies apply everywhere. Advertising regulators differ by country:
a creator in Mumbai with a mostly Indian audience answers to ASCI's guidelines,
a US audience brings in the FTC's Endorsement Guides, a UK audience the ASA's
CAP Code and the CMA's guidance. A review can target one or several markets;
each adds that regulator's rules from the knowledge base and its expectations
about disclosure labels.

The tool does not decide which jurisdiction applies. The creator picks the
markets; everything from a market pack is advisory.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

DEFAULT_MARKETS: tuple[str, ...] = ("IN",)


@dataclass(frozen=True)
class MarketInfo:
    id: str
    label: str
    regulator: str
    # Knowledge-base platform holding this market's rules.
    kb_platform: str
    summary: str

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "regulator": self.regulator,
            "summary": self.summary,
            # Policy-library platform that holds this market's rules.
            "kb_platform": self.kb_platform,
        }


MARKETS: dict[str, MarketInfo] = {
    m.id: m
    for m in (
        MarketInfo(
            "IN",
            "India",
            "ASCI",
            "india_advisory",
            "ASCI influencer advertising guidelines",
        ),
        MarketInfo(
            "US",
            "United States",
            "FTC",
            "us_advisory",
            "FTC Endorsement Guides and disclosure guidance",
        ),
        MarketInfo(
            "UK",
            "United Kingdom",
            "ASA / CMA",
            "uk_advisory",
            "ASA CAP Code and CMA guidance on hidden advertising",
        ),
    )
}


class UnknownMarket(ValueError):
    pass


def clean(values: Iterable[str] | None, default: Iterable[str] = DEFAULT_MARKETS) -> list[str]:
    """Validated, de-duplicated market IDs in registry order. Empty input -> ``default``."""
    wanted = {str(v).strip().upper() for v in (values or []) if str(v).strip()}
    if not wanted:
        wanted = {str(v).upper() for v in default}
    unknown = sorted(wanted - set(MARKETS))
    if unknown:
        raise UnknownMarket(
            f"Unknown market: {', '.join(unknown)}. Choose from {', '.join(MARKETS)}."
        )
    return [m for m in MARKETS if m in wanted]


def kb_platforms(markets: Iterable[str]) -> set[str]:
    return {MARKETS[m].kb_platform for m in markets if m in MARKETS}


def names(markets: Iterable[str]) -> str:
    """'India and the United States' for prose."""
    labels = [
        ("the " if MARKETS[m].label.startswith("United") else "") + MARKETS[m].label
        for m in markets
        if m in MARKETS
    ]
    if len(labels) <= 1:
        return "".join(labels)
    return ", ".join(labels[:-1]) + " and " + labels[-1]
