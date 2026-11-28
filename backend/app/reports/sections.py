"""Which report section a finding belongs in.

Disclosure stays in its own section. Community-guideline risk flags, harmful-content
findings, and older checks that already cite a community-guideline or
advertiser-suitability rule (medical claims, hashtag abuse, cover bait) sit in
the Community guidelines section. Licensing and originality stay in Other.
"""

from __future__ import annotations

from typing import Literal

ReportSection = Literal["community", "disclosure", "brief", "other"]

_COMMUNITY_EXACT = {"YT-MON-AD-FRIENDLY", "YT-HASHTAGS"}


def section_for(category: str, policy_rule_ids: list[str]) -> ReportSection:
    if category == "disclosure":
        return "disclosure"
    if category == "brand_brief":
        return "brief"
    if category in {"community_guidelines", "harmful_content"}:
        return "community"
    for rule_id in policy_rule_ids:
        if rule_id in _COMMUNITY_EXACT or rule_id.startswith(("YT-CG-", "META-CS-", "TT-CG-")):
            return "community"
    return "other"
