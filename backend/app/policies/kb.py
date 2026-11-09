"""Versioned policy knowledge base.

Rule IDs (e.g. ``YT-CG-SPAM``) are CreatorShield's own stable identifiers -
the platforms do not publish rule numbers. Each rule maps to one official
policy page (``official_url``) with the date we last verified its content.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

RulePlatform = Literal["youtube", "instagram", "meta_all", "india_advisory"]

OFFICIAL_HOSTS = {
    "support.google.com",
    "help.instagram.com",
    "transparency.meta.com",
    "www.facebook.com",
    "about.fb.com",
    "www.ascionline.in",
    "ascionline.in",
}

# Which knowledge-base platforms apply to each target platform.
TARGET_PLATFORMS: dict[str, set[str]] = {
    "youtube_shorts": {"youtube", "india_advisory"},
    "instagram_reels": {"instagram", "meta_all", "india_advisory"},
}


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

    def rules_for_platform(self, target: str) -> list[PolicyRule]:
        allowed = TARGET_PLATFORMS[target]
        return [r for r in self.rules if r.platform in allowed]

    def applies(self, rule_id: str, target: str) -> bool:
        rule = self.get(rule_id)
        return rule is not None and rule.platform in TARGET_PLATFORMS[target]


def load_kb(path: Path) -> PolicyKB:
    with path.open(encoding="utf-8") as fh:
        return PolicyKB.model_validate(yaml.safe_load(fh))


@lru_cache
def get_kb(path: str) -> PolicyKB:
    return load_kb(Path(path))
