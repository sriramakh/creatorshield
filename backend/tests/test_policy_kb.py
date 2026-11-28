from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app import markets as market_registry
from app.analysis.deterministic import MARKET_RULES, rules_for
from app.config import get_settings
from app.policies.kb import OFFICIAL_HOSTS, PolicyKB, load_kb


@pytest.fixture(scope="module")
def kb() -> PolicyKB:
    return load_kb(get_settings().policy_kb_path)


def test_kb_loads_and_every_rule_is_official_and_dated(kb: PolicyKB) -> None:
    assert len(kb.rules) >= 30
    for rule in kb.rules:
        assert rule.official_url.host in OFFICIAL_HOSTS
        assert rule.verified_on is not None
        assert rule.key_points


def test_deterministic_checks_only_cite_rules_that_exist_for_the_platform(kb: PolicyKB) -> None:
    from app.api.creator import available_platforms

    every_market = list(market_registry.MARKETS)
    for platform in available_platforms():
        for ids in rules_for(platform, every_market).values():
            for rule_id in ids:
                assert kb.applies(rule_id, platform, every_market), (
                    f"{rule_id} not valid for {platform}"
                )
    # A market's rules are only citable when that market is selected.
    for market, groups in MARKET_RULES.items():
        others = [m for m in every_market if m != market]
        for ids in groups.values():
            for rule_id in ids:
                assert kb.applies(rule_id, "youtube_shorts", [market])
                assert not kb.applies(rule_id, "youtube_shorts", others)


def test_platform_scoping(kb: PolicyKB) -> None:
    yt = {r.id for r in kb.rules_for_platform("youtube_shorts")}
    ig = {r.id for r in kb.rules_for_platform("instagram_reels")}
    assert "YT-CG-SPAM" in yt and "YT-CG-SPAM" not in ig
    assert "META-CS-SPAM" in ig and "META-CS-SPAM" not in yt
    assert "IN-ASCI-INFLUENCER" in yt and "IN-ASCI-INFLUENCER" in ig


def _base_rule(**overrides: object) -> dict[str, object]:
    rule = {
        "id": "YT-TEST-ONE",
        "platform": "youtube",
        "category": "spam_deception",
        "title": "t",
        "official_title": "t",
        "official_url": "https://support.google.com/youtube/answer/1",
        "verified_on": "2026-10-21",
        "key_points": ["x"],
    }
    rule.update(overrides)
    return rule


def test_kb_rejects_non_official_domains() -> None:
    with pytest.raises(ValidationError):
        PolicyKB.model_validate(
            {
                "version": "x",
                "verified_on": "2026-10-21",
                "rules": [_base_rule(official_url="https://example.com/policy")],
            }
        )


def test_kb_rejects_duplicate_ids() -> None:
    with pytest.raises(ValidationError):
        PolicyKB.model_validate(
            {
                "version": "x",
                "verified_on": "2026-10-21",
                "rules": [_base_rule(), _base_rule()],
            }
        )


def test_kb_file_is_plain_yaml(tmp_path: Path) -> None:
    raw = yaml.safe_load(get_settings().policy_kb_path.read_text(encoding="utf-8"))
    assert raw["version"]


@pytest.mark.parametrize(
    "url",
    [
        "http://support.google.com/youtube/answer/2801973",  # not https
        "https://support.google.com.evil.com/youtube/answer/1",  # look-alike host
        "https://youtube.com.evil.com/policy",
        "https://evil.com/support.google.com",
    ],
)
def test_kb_requires_https_on_an_official_host(url: str) -> None:
    with pytest.raises(ValidationError):
        PolicyKB.model_validate(
            {"version": "x", "verified_on": "2026-10-21", "rules": [_base_rule(official_url=url)]}
        )
