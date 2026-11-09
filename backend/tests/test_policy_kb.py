from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.analysis.deterministic import PLATFORM_RULES
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
    for platform, groups in PLATFORM_RULES.items():
        for ids in groups.values():
            for rule_id in ids:
                assert kb.applies(rule_id, platform), f"{rule_id} not valid for {platform}"


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
    raw = yaml.safe_load(get_settings().policy_kb_path.read_text())
    assert raw["version"]
