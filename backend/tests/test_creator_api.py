"""Creator features through the API: caption check, markets, briefs, settings, insights."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.analysis.deterministic import run_deterministic_checks
from app.db import get_sessionmaker
from app.jobs import purge_expired
from app.main import app
from app.models import AnalysisStat

PROMO = "Loving my new GlowUp serum. Use code GLOW20 for 20% off"


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def check(client: TestClient, **body: Any) -> dict[str, Any]:
    payload = {"platform": "instagram_reels", "caption": PROMO, "hashtags": []}
    payload.update(body)
    res = client.post("/api/quick-check", json=payload)
    assert res.status_code == 200, res.text
    return res.json()


def upload(client: TestClient, path: Path, **data: str):  # type: ignore[no-untyped-def]
    form = {"platform": "instagram_reels", "language": "en", "caption": "", "hashtags": ""}
    form.update(data)
    with path.open("rb") as fh:
        return client.post("/api/analyses", files={"file": (path.name, fh, "video/mp4")}, data=form)


# ---- configuration -----------------------------------------------------------


def test_config_lists_platforms_and_markets_that_have_rules(client: TestClient) -> None:
    config = client.get("/api/config").json()
    platforms = {p["id"]: p for p in config["platforms"]}
    assert set(platforms) == {"youtube_shorts", "youtube_video", "instagram_reels"}
    # TikTok has no verified rules in the knowledge base, so it is not offered.
    assert "tiktok" not in platforms
    assert platforms["youtube_video"]["family"] == "youtube"
    assert [m["id"] for m in config["markets"]] == ["IN", "US", "UK"]
    assert config["default_markets"] == ["IN"]
    assert config["limits"]["brief_items_max"] == 20
    assert config["catalogue_max_seconds"] > 0


def test_policy_library_holds_the_market_packs(client: TestClient) -> None:
    rules = client.get("/api/policies").json()["rules"]
    by_platform: dict[str, int] = {}
    for rule in rules:
        by_platform[rule["platform"]] = by_platform.get(rule["platform"], 0) + 1
    assert by_platform["us_advisory"] == 9
    assert by_platform["uk_advisory"] == 8
    assert by_platform["india_advisory"] == 5
    assert "tiktok" not in by_platform


# ---- instant caption check ---------------------------------------------------


def test_quick_check_flags_undisclosed_promotion_and_suggests_a_caption(
    client: TestClient,
) -> None:
    body = check(client, sponsorship={"relationship": "paid", "sponsors": ["GlowUp"]})
    assert body["markets"] == ["IN"]
    titles = [f["title"] for f in body["findings"]]
    assert "Promotional language without a visible sponsorship disclosure" in titles
    assert all(f["finding_type"] != "cannot_check" for f in body["findings"])
    assert body["readiness"]["verdict"] == "fix_first"
    disclosure = next(c for c in body["readiness"]["checklist"] if c["key"] == "disclosure")
    assert disclosure["status"] == "fail" and disclosure["finding_ids"]
    fix = body["caption_fix"]
    assert fix["needed"] is True
    # The caption already names the sponsor, so only the label is added.
    assert fix["suggested_caption"] == "Ad: " + PROMO
    assert body["not_checked"]
    # Every citation resolves to a verified rule.
    for finding in body["findings"]:
        assert len(finding["policies"]) == len(finding["policy_rule_ids"])

    # The suggested caption clears the same check.
    fixed = check(
        client,
        caption=fix["suggested_caption"],
        sponsorship={"relationship": "paid", "sponsors": ["GlowUp"]},
    )
    assert "Promotional language without a visible sponsorship disclosure" not in [
        f["title"] for f in fixed["findings"]
    ]
    assert fixed["caption_fix"]["needed"] is False
    assert fixed["readiness"]["verdict"] != "fix_first"


def test_quick_check_is_market_aware(client: TestClient) -> None:
    caption = "Sponsored by GlowUp. Use code GLOW20 for 20% off"
    india = check(client, caption=caption, markets=["IN"])
    assert not [f for f in india["findings"] if "may not be clear enough" in f["title"]]
    assert india["market_disclosure"]["by_market"]["IN"]["status"] == "clear"

    uk = check(client, caption=caption, markets=["IN", "UK"])
    finding = next(f for f in uk["findings"] if "may not be clear enough" in f["title"])
    assert finding["title"].endswith("the United Kingdom")
    assert finding["category"] == "disclosure"
    cited = set(finding["policy_rule_ids"])
    assert cited == {"UK-ASA-INFLUENCER-GUIDE", "UK-CMA-HIDDEN-ADS", "UK-CAP-CODE-S2"}
    assert {p["platform"] for p in finding["policies"]} == {"uk_advisory"}
    assert uk["market_disclosure"]["by_market"]["UK"]["status"] == "unclear"
    assert uk["caption_fix"]["needed"] is True
    assert uk["caption_fix"]["suggested_caption"].startswith("Ad: ")


def test_market_rules_are_cited_only_for_selected_markets() -> None:
    def cited(markets: list[str]) -> set[str]:
        drafts = run_deterministic_checks("youtube_shorts", PROMO, [], {}, 0.0, markets=markets)
        finding = next(d for d in drafts if d.title.startswith("Promotional language"))
        return set(finding.policy_rule_ids)

    assert cited(["IN"]) == {"YT-DISC-PAID-PROMO", "IN-ASCI-INFLUENCER", "IN-CCPA-ENDORSE"}
    us = cited(["US"])
    assert "US-FTC-DISCLOSURES-101" in us and "IN-ASCI-INFLUENCER" not in us
    everything = cited(["IN", "US", "UK"])
    assert {"IN-ASCI-INFLUENCER", "US-FTC-FAQ-HOW", "UK-CMA-HIDDEN-ADS"} <= everything


def test_shorthand_labels_are_named_in_the_finding() -> None:
    drafts = run_deterministic_checks(
        "instagram_reels", "New drop, code GLOW20 #sp #gifted", [], {}, 0.0, markets=["US", "UK"]
    )
    finding = next(d for d in drafts if d.title.startswith("Promotional language"))
    assert '"#sp" and "#gifted"' in finding.explanation
    assert "FTC and ASA / CMA guidance does not treat" in finding.explanation


def test_quick_check_rejects_unknown_platform_and_market(client: TestClient) -> None:
    bad_platform = client.post("/api/quick-check", json={"platform": "tiktok", "caption": "hi"})
    assert bad_platform.status_code == 422
    assert "youtube_shorts, youtube_video or instagram_reels" in bad_platform.text
    bad_market = client.post(
        "/api/quick-check", json={"platform": "youtube_shorts", "caption": "hi", "markets": ["FR"]}
    )
    assert bad_market.status_code == 422 and "Unknown market" in bad_market.text
    too_long = client.post(
        "/api/quick-check", json={"platform": "youtube_shorts", "caption": "x" * 5001}
    )
    assert too_long.status_code == 422


def test_quick_check_with_an_inline_brief(client: TestClient) -> None:
    body = check(
        client,
        caption="Ad: my routine with GlowUp, it cures acne #GlowUpPartner",
        brief={
            "brand": "GlowUp",
            "must_say": ["patch test first"],
            "must_not_say": ["cures acne"],
            "required_hashtags": ["GlowUpPartner"],
            "required_mentions": ["glowup"],
        },
    )
    statuses = {(i["kind"], i["text"]): i["status"] for i in body["brief_check"]["items"]}
    assert statuses[("must_not_say", "cures acne")] == "violated"
    assert statuses[("required_hashtag", "#GlowUpPartner")] == "met"
    assert statuses[("required_mention", "@glowup")] == "missing"
    # A line that must be spoken cannot be confirmed from a caption.
    assert statuses[("must_say", "patch test first")] == "unverified"
    brief_findings = [f for f in body["findings"] if f["category"] == "brand_brief"]
    assert {f["report_section"] for f in brief_findings} == {"brief"}
    assert all(f["policy_rule_ids"] == [] for f in brief_findings)
    row = next(c for c in body["readiness"]["checklist"] if c["key"] == "brief")
    assert row["status"] == "fail"
    assert body["readiness"]["verdict"] == "fix_first"


def test_brief_findings_do_not_move_the_policy_risk_indicator(client: TestClient) -> None:
    clean = check(client, caption="Ad: my routine with GlowUp")
    with_brief = check(
        client,
        caption="Ad: my routine with GlowUp",
        brief={"brand": "GlowUp", "required_hashtags": ["GlowUpPartner"]},
    )
    assert with_brief["risk_score"] == clean["risk_score"]
    assert with_brief["readiness"]["verdict"] == "fix_first"


# ---- saved briefs ------------------------------------------------------------


def test_brief_crud_and_use_by_id(client: TestClient) -> None:
    created = client.post(
        "/api/briefs",
        json={
            "name": "GlowUp Q4",
            "brand": "GlowUp",
            "must_not_say": ["miracle"],
            "required_hashtags": ["#GlowUpPartner", "glowuppartner"],
            "required_disclosure": "#ad",
        },
    )
    assert created.status_code == 201, created.text
    brief = created.json()
    assert brief["required_hashtags"] == ["GlowUpPartner"]
    assert brief["must_say"] == []

    listed = client.get("/api/briefs").json()
    assert [b["id"] for b in listed] == [brief["id"]]

    updated = client.put(
        f"/api/briefs/{brief['id']}",
        json={"name": "GlowUp Q4 v2", "brand": "GlowUp", "must_not_say": ["miracle", "cure"]},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "GlowUp Q4 v2"
    assert updated.json()["required_disclosure"] is None

    body = check(client, caption="A miracle serum", brief_id=brief["id"])
    assert body["brief_check"]["failed"] == 1

    both = client.post(
        "/api/quick-check",
        json={
            "platform": "instagram_reels",
            "caption": "x",
            "brief_id": brief["id"],
            "brief": {"must_say": ["y"]},
        },
    )
    assert both.status_code == 422

    assert client.delete(f"/api/briefs/{brief['id']}").status_code == 204
    assert client.get("/api/briefs").json() == []
    assert client.delete(f"/api/briefs/{brief['id']}").status_code == 404
    gone = client.post(
        "/api/quick-check",
        json={"platform": "instagram_reels", "caption": "x", "brief_id": brief["id"]},
    )
    assert gone.status_code == 404


def test_brief_validation_messages(client: TestClient) -> None:
    no_name = client.post("/api/briefs", json={"must_say": ["x"]})
    assert no_name.status_code == 422 and "name" in no_name.json()["detail"]
    empty = client.post("/api/briefs", json={"name": "Empty"})
    assert empty.status_code == 422 and "at least one requirement" in empty.json()["detail"]
    too_many = client.post(
        "/api/briefs", json={"name": "Big", "must_say": [f"line {i}" for i in range(21)]}
    )
    assert too_many.status_code == 422 and "at most 20" in too_many.json()["detail"]


# ---- workspace settings ------------------------------------------------------


def test_workspace_settings_defaults_and_updates(client: TestClient) -> None:
    initial = client.get("/api/settings").json()
    assert initial == {
        "mode": "creator",
        "display_name": "",
        "default_platform": "instagram_reels",
        "default_markets": ["IN"],
        "default_language": "en",
        "onboarded": False,
    }
    updated = client.put(
        "/api/settings",
        json={
            "mode": "agency",
            "display_name": "  Northlight Talent ",
            "default_platform": "youtube_video",
            "default_markets": ["uk", "US"],
            "onboarded": True,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["display_name"] == "Northlight Talent"
    assert updated.json()["default_markets"] == ["US", "UK"]
    assert client.get("/api/settings").json()["mode"] == "agency"

    # The workspace default is used when a check does not choose markets.
    assert check(client)["markets"] == ["US", "UK"]

    assert client.put("/api/settings", json={"default_platform": "tiktok"}).status_code == 422
    assert client.put("/api/settings", json={"default_markets": ["FR"]}).status_code == 422
    assert client.put("/api/settings", json={"default_markets": []}).status_code == 422
    assert client.put("/api/settings", json={"mode": "enterprise"}).status_code == 422
    # A rejected update changes nothing.
    assert client.get("/api/settings").json()["default_platform"] == "youtube_video"


# ---- full review with markets and a brief ------------------------------------


@pytest.mark.slow
def test_review_with_markets_brief_readiness_and_insights(
    client: TestClient, sample_promo_en: Path
) -> None:
    res = upload(
        client,
        sample_promo_en,
        caption="Sponsored by GlowUp. Use code GLOW20 for 20% off",
        markets="US, UK",
        client_label="Client A",
        brief='{"brand": "GlowUp", "required_hashtags": ["GlowUpPartner"], '
        '"must_not_say": ["zzz-not-said"]}',
    )
    assert res.status_code == 202, res.text
    aid = res.json()["id"]
    a = client.get(f"/api/analyses/{aid}").json()
    assert a["status"] == "completed"
    assert a["markets"] == ["US", "UK"]
    assert a["brief"]["brand"] == "GlowUp"
    assert a["brief_check"]["scope"] == "video"
    assert a["brief_check"]["failed"] == 1

    titles = [f["title"] for f in a["findings"]]
    assert "Disclosure label may not be clear enough for the United Kingdom" in titles
    assert "Brand brief: required hashtags are missing" in titles
    # India was not selected, so no ASCI rule is cited anywhere.
    assert not [r for f in a["findings"] for r in f["policy_rule_ids"] if r.startswith("IN-")]

    readiness = a["readiness"]
    assert readiness["verdict"] == a["readiness_verdict"] == "fix_first"
    keys = [c["key"] for c in readiness["checklist"]]
    assert keys[:5] == ["disclosure", "community", "claims", "rights", "brief"]
    assert next(c for c in readiness["checklist"] if c["key"] == "brief")["status"] == "fail"
    # Mock AI is not a real review, and the checklist says so.
    assert next(c for c in readiness["checklist"] if c["key"] == "ai_review")["status"] == "warn"
    assert a["caption_fix"]["needed"] is True
    assert a["market_disclosure"]["by_market"]["UK"]["status"] == "unclear"
    assert any("Advertising guidance applied: FTC" in note for note in a["limitations"])

    listed = client.get("/api/analyses").json()
    assert listed[0]["readiness_verdict"] == "fix_first"
    assert listed[0]["markets"] == ["US", "UK"]

    html = client.get(f"/api/analyses/{aid}/report.html").text
    assert "Before you post: Fix before posting" in html
    assert "Brand brief: GlowUp (1 of 2 met)" in html
    assert "United States (FTC), United Kingdom (ASA / CMA)" in html
    assert "Suggested caption" in html

    stats = client.get("/api/insights?days=30").json()
    assert stats["totals"]["reviews"] == 1
    assert stats["totals"]["fix_first"] == 1 and stats["totals"]["ready_rate"] == 0
    assert stats["by_day"][-1]["reviews"] == 1 and len(stats["by_day"]) == 31
    groups = {g["group"]: g for g in stats["by_group"]}
    assert groups["disclosure"]["findings"] >= 1 and groups["brief"]["findings"] == 1
    assert stats["by_platform"][0]["platform"] == "instagram_reels"
    assert {m["market"] for m in stats["by_market"]} == {"US", "UK"}
    assert stats["by_client"][0]["client_label"] == "Client A"

    # Retention removes the review but keeps its outcome for insights.
    with get_sessionmaker()() as db:
        purge_expired(db, now=datetime.now(UTC) + timedelta(days=30))
        assert db.get(AnalysisStat, __import__("uuid").UUID(aid)) is not None
    assert client.get(f"/api/analyses/{aid}").status_code == 404
    assert client.get("/api/insights?days=30").json()["totals"]["reviews"] == 1


@pytest.mark.slow
def test_explicit_delete_removes_the_review_from_insights(
    client: TestClient, sample_promo_en: Path
) -> None:
    aid = upload(client, sample_promo_en, platform="youtube_video").json()["id"]
    assert client.get(f"/api/analyses/{aid}").json()["platform"] == "youtube_video"
    assert client.get("/api/insights").json()["totals"]["reviews"] == 1
    assert client.delete(f"/api/analyses/{aid}").status_code == 204
    assert client.get("/api/insights").json()["totals"]["reviews"] == 0


def test_upload_rejects_bad_markets_brief_and_platform(
    client: TestClient, sample_promo_en: Path
) -> None:
    assert upload(client, sample_promo_en, markets="FR").status_code == 422
    assert upload(client, sample_promo_en, brief="not json").status_code == 422
    assert upload(client, sample_promo_en, brief="[1]").status_code == 422
    assert upload(client, sample_promo_en, brief_id="nope").status_code == 422
    assert upload(client, sample_promo_en, platform="tiktok").status_code == 422
    too_long = '{"must_say": ["' + "x" * 201 + '"]}'
    assert upload(client, sample_promo_en, brief=too_long).status_code == 422
    assert client.get("/api/analyses").json() == []


def test_insights_window_validation_and_empty_state(client: TestClient) -> None:
    assert client.get("/api/insights?days=3").status_code == 422
    empty = client.get("/api/insights?days=7").json()
    assert empty["totals"] == {
        "reviews": 0,
        "ready": 0,
        "review": 0,
        "fix_first": 0,
        "ready_rate": None,
        "avg_risk_score": None,
        "open_findings": 0,
    }
    assert len(empty["by_day"]) == 8


@pytest.mark.parametrize(
    ("method", "path"),
    [("PUT", "/api/settings"), ("PUT", "/api/briefs/x"), ("POST", "/api/quick-check")],
)
def test_browser_preflight_allows_the_methods_the_app_uses(
    client: TestClient, method: str, path: str
) -> None:
    """The dev frontend runs on another origin, so every method it uses must pass CORS."""
    res = client.options(
        path,
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert res.status_code == 200, res.text
    assert method in res.headers["access-control-allow-methods"]
    assert res.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_every_api_method_is_allowed_by_cors() -> None:
    """A route added with a new HTTP method must not be unreachable from the browser."""
    from starlette.middleware.cors import CORSMiddleware

    cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
    allowed = set(cors.kwargs["allow_methods"])
    used = {
        method
        for route in app.routes
        if getattr(route, "path", "").startswith("/api")
        for method in getattr(route, "methods", set())
    } - {"HEAD", "OPTIONS"}
    assert used <= allowed, f"not allowed by CORS: {sorted(used - allowed)}"


def test_first_requests_arriving_together_do_not_fail(client: TestClient) -> None:
    """The app loads settings from several requests at once on a fresh workspace."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda _: client.get("/api/settings").status_code, range(16)))
    assert codes == [200] * 16
    assert client.get("/api/settings").json()["onboarded"] is False
