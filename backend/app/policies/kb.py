"""Versioned policy knowledge base.

Rule IDs (e.g. ``YT-CG-SPAM``) are CreatorShield's own stable identifiers -
the platforms do not publish rule numbers. Each rule maps to one official
policy page (``official_url``) with the date we last verified its content.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from app import markets as market_registry
from app.platforms import PLATFORMS

RulePlatform = Literal[
    "youtube",
    "instagram",
    "meta_all",
    "tiktok",
    "india_advisory",
    "us_advisory",
    "uk_advisory",
]

OFFICIAL_HOSTS = {
    "support.google.com",
    "help.instagram.com",
    "transparency.meta.com",
    "www.facebook.com",
    "about.fb.com",
    "www.ascionline.in",
    "ascionline.in",
    # Advertising regulators (market packs)
    "www.ftc.gov",
    "www.ecfr.gov",
    "www.asa.org.uk",
    "www.gov.uk",
    "consumeraffairs.gov.in",
    "ccpa.doca.gov.in",
    "www.sebi.gov.in",
    # TikTok (no rules are loaded until its policy pages have been read)
    "www.tiktok.com",
    "support.tiktok.com",
}


def kb_platforms_for(
    target: str, markets: Iterable[str] = market_registry.DEFAULT_MARKETS
) -> set[str]:
    """Knowledge-base platforms that apply to a target platform and its audience markets."""
    return set(PLATFORMS[target].kb_platforms) | market_registry.kb_platforms(markets)


class PolicyRule(BaseModel):
    id: str = Field(pattern=r"^[A-Z]{2,5}(-[A-Z0-9]+)+$")
    platform: RulePlatform
    category: str
    title: str
    official_title: str
    official_url: HttpUrl
    verified_on: date
    key_points: list[str] = Field(min_length=1)
    quote: str | None = None

    @field_validator("official_url")
    @classmethod
    def _official_host(cls, v: HttpUrl) -> HttpUrl:
        if v.scheme != "https":
            raise ValueError(f"{v} must use https")
        if v.host not in OFFICIAL_HOSTS:
            raise ValueError(f"{v} is not an official platform policy domain")
        return v


class PolicyKB(BaseModel):
    version: str
    verified_on: date
    notes: str = ""
    rules: list[PolicyRule]

    @model_validator(mode="after")
    def _unique_ids(self) -> PolicyKB:
        ids = [r.id for r in self.rules]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate rule ids: {sorted(dupes)}")
        return self

    def get(self, rule_id: str) -> PolicyRule | None:
        return next((r for r in self.rules if r.id == rule_id), None)

    def rules_for_platform(
        self, target: str, markets: Iterable[str] = market_registry.DEFAULT_MARKETS
    ) -> list[PolicyRule]:
        allowed = kb_platforms_for(target, markets)
        return [r for r in self.rules if r.platform in allowed]

    def applies(
        self,
        rule_id: str,
        target: str,
        markets: Iterable[str] = market_registry.DEFAULT_MARKETS,
    ) -> bool:
        rule = self.get(rule_id)
        return rule is not None and rule.platform in kb_platforms_for(target, markets)

    def platforms_present(self) -> set[str]:
        return {r.platform for r in self.rules}

    def existing(self, rule_ids: Iterable[str]) -> list[str]:
        """The given rule IDs that are in this knowledge base, in order."""
        return [r for r in rule_ids if self.get(r) is not None]


def load_kb(path: Path) -> PolicyKB:
    with path.open(encoding="utf-8") as fh:
        return PolicyKB.model_validate(yaml.safe_load(fh))


@lru_cache
def get_kb(path: str) -> PolicyKB:
    return load_kb(Path(path))
