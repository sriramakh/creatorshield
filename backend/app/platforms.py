"""Target platforms a review can be made for.

One registry so the API, the checks, the prompt and the report agree on what
exists. ``family`` is what most rules key on: Shorts and long-form YouTube
share YouTube's policies; Reels use Instagram's and Meta's.

A platform is only offered when the policy knowledge base holds rules for it
(see :func:`available`), so a target never ships without citable policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Family = Literal["youtube", "instagram", "tiktok"]


@dataclass(frozen=True)
class PlatformInfo:
    id: str
    label: str
    short_label: str
    family: Family
    # Knowledge-base platforms whose rules apply (markets add their own).
    kb_platforms: frozenset[str]
    description: str
    # Short vertical video; drives Shorts/Reels-specific notes.
    short_form: bool
    disclosure_setting: str

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "short_label": self.short_label,
            "family": self.family,
            "description": self.description,
            "short_form": self.short_form,
        }


PLATFORMS: dict[str, PlatformInfo] = {
    p.id: p
    for p in (
        PlatformInfo(
            "youtube_shorts",
            "YouTube Shorts",
            "Shorts",
            "youtube",
            frozenset({"youtube"}),
            "Community Guidelines, monetisation and paid-promotion rules",
            True,
            "YouTube's paid promotion setting",
        ),
        PlatformInfo(
            "youtube_video",
            "YouTube video",
            "YouTube",
            "youtube",
            frozenset({"youtube"}),
            "Long-form uploads: Community Guidelines, advertiser-friendly and paid-promotion rules",
            False,
            "YouTube's paid promotion setting",
        ),
        PlatformInfo(
            "instagram_reels",
            "Instagram Reels",
            "Reels",
            "instagram",
            frozenset({"instagram", "meta_all"}),
            "Meta Community Standards and Instagram branded-content rules",
            True,
            "Instagram's Paid partnership label",
        ),
        PlatformInfo(
            "tiktok",
            "TikTok",
            "TikTok",
            "tiktok",
            frozenset({"tiktok"}),
            "Community Guidelines and branded-content rules",
            True,
            "TikTok's content disclosure setting",
        ),
    )
}

PLATFORM_NAMES: dict[str, str] = {p.id: p.label for p in PLATFORMS.values()}


def get(platform: str) -> PlatformInfo:
    return PLATFORMS[platform]


def family(platform: str) -> Family:
    return PLATFORMS[platform].family


def is_youtube(platform: str) -> bool:
    return PLATFORMS[platform].family == "youtube"


def available(kb_platforms: set[str]) -> list[PlatformInfo]:
    """Platforms whose policies are in the knowledge base."""
    return [p for p in PLATFORMS.values() if p.kb_platforms & kb_platforms]


def describe(ids: list[str] | set[str]) -> str:
    """'youtube_shorts, instagram_reels or tiktok' for error messages."""
    ordered = [p for p in PLATFORMS if p in ids]
    if len(ordered) <= 1:
        return "".join(ordered)
    return ", ".join(ordered[:-1]) + " or " + ordered[-1]
