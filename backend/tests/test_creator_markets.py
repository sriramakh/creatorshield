"""Market-aware disclosure labels and the suggested caption."""

from __future__ import annotations

import pytest

from app import markets as market_registry
from app.analysis.caption_fix import suggest
from app.analysis.market_disclosure import ACCEPTED, UNIVERSAL_LABEL, assess, find_labels

ALL = ["IN", "US", "UK"]
EVERYWHERE_UNCLEAR = {"IN": "unclear", "US": "unclear", "UK": "unclear"}
EVERYWHERE_CLEAR = {"IN": "clear", "US": "clear", "UK": "clear"}
NOWHERE = {"IN": "none", "US": "none", "UK": "none"}


def _status(caption: str, markets: list[str] | None = None) -> dict[str, str]:
    result = assess(caption, markets or ALL)
    return {m: v["status"] for m, v in result["by_market"].items()}


@pytest.mark.parametrize(
    ("caption", "expected"),
    [
        ("#ad Loving this serum", EVERYWHERE_CLEAR),
        ("Advertisement feature: my routine", EVERYWHERE_CLEAR),
        ("#advertising new drop", EVERYWHERE_CLEAR),
        # "Sponsored" is on ASCI's and the FTC's lists; the ASA advises against it.
        ("Sponsored by Glow. Code GLOW20", {"IN": "clear", "US": "clear", "UK": "unclear"}),
        ("Paid partnership with Glow", {"IN": "clear", "US": "clear", "UK": "unclear"}),
        # ASCI permits "Collaboration"; the FTC calls "collab" vague; the ASA advises against it.
        ("#collab with Glow", {"IN": "clear", "US": "unclear", "UK": "unclear"}),
        ("Collab: new drop", {"IN": "clear", "US": "unclear", "UK": "unclear"}),
        ("Partnership with Glow: my routine", {"IN": "clear", "US": "clear", "UK": "unclear"}),
        # Shorthand no regulator lists as clear.
        ("Loving this serum #sp #gifted", EVERYWHERE_UNCLEAR),
        ("Thanks to Glow for the gift #ambassador", EVERYWHERE_UNCLEAR),
        ("In association with Glow", EVERYWHERE_UNCLEAR),
        # A clear label that a viewer has to expand the caption to see.
        ("Great day " + "x" * 100 + " #ad", {"IN": "buried", "US": "buried", "UK": "buried"}),
        # Denials and plain captions carry no label.
        ("Not sponsored. I bought it myself", NOWHERE),
        ("Just my morning routine", NOWHERE),
    ],
)
def test_label_status_per_market(caption: str, expected: dict[str, str]) -> None:
    assert _status(caption) == expected


def test_universal_label_is_accepted_everywhere() -> None:
    assert all("ad" in kinds for kinds in ACCEPTED.values())
    assert set(ACCEPTED) == set(market_registry.MARKETS)
    assert _status(f"{UNIVERSAL_LABEL}: my routine") == EVERYWHERE_CLEAR


def test_labels_report_where_they_are_clear() -> None:
    labels = assess("Sponsored by Glow #sp", ALL)["labels"]
    sponsored = next(x for x in labels if x["kind"] == "sponsored")
    assert sponsored["clear_in"] == ["IN", "US"]
    assert sponsored["unclear_in"] == ["UK"]
    shorthand = next(x for x in labels if x["kind"] == "sp")
    assert shorthand["clear_in"] == []
    assert shorthand["unclear_in"] == ALL
    denied = find_labels("This is not an ad: just a review")
    assert [f.denied for f in denied] == [True]


def test_only_selected_markets_are_assessed() -> None:
    assert _status("#collab with Glow", ["IN"]) == {"IN": "clear"}


def test_market_registry_cleans_input() -> None:
    assert market_registry.clean(["uk", " in ", "UK"]) == ["IN", "UK"]
    assert market_registry.clean([]) == ["IN"]
    assert market_registry.clean(None, default=["US"]) == ["US"]
    with pytest.raises(market_registry.UnknownMarket):
        market_registry.clean(["FR"])
    assert market_registry.names(ALL) == "India, the United States and the United Kingdom"


# ---- suggested caption -------------------------------------------------------


def test_no_commercial_signal_means_no_suggestion() -> None:
    result = suggest("Just my morning routine", [], "instagram_reels", ALL)
    assert result["needed"] is False
    assert result["suggested_caption"] == "Just my morning routine"
    assert "No promotion wording" in result["note"]


def test_promo_without_label_gets_ad_and_the_sponsor_named() -> None:
    result = suggest(
        "Loving my new serum, code GLOW20",
        ["skincare"],
        "instagram_reels",
        ALL,
        {"relationship": "paid", "sponsors": ["Glow"]},
        promo_detected=True,
    )
    assert result["needed"] is True
    assert result["suggested_caption"] == (
        "Ad: paid partnership with Glow. Loving my new serum, code GLOW20"
    )
    assert result["label"] == "Ad"
    assert result["changes"][0] == 'Opened the caption with "Ad"'
    assert "Named Glow next to the label" in result["changes"]
    assert "Instagram's Paid partnership label" in result["note"]
    assert "not legal advice" in result["note"]
    # The suggestion itself passes the same assessment.
    assert _status(result["suggested_caption"]) == EVERYWHERE_CLEAR


def test_label_that_is_unclear_in_one_market_is_replaced() -> None:
    result = suggest("Collab: new drop with Glow", [], "youtube_shorts", ["IN", "UK"])
    assert result["needed"] is True
    assert result["suggested_caption"] == "Ad: new drop with Glow"
    assert any("ASA / CMA guidance does not treat as clear" in c for c in result["changes"])
    # For India alone the same caption already opens with a permitted label.
    india = suggest("Collab: new drop with Glow", [], "youtube_shorts", ["IN"])
    assert india["needed"] is False
    assert india["markets"] == {"IN": "clear"}


def test_clear_opening_label_with_sponsor_named_needs_nothing() -> None:
    result = suggest(
        "#ad morning with Glow",
        [],
        "instagram_reels",
        ALL,
        {"relationship": "paid", "sponsors": ["Glow"]},
    )
    assert result["needed"] is False
    assert result["suggested_caption"] == "#ad morning with Glow"


def test_several_sponsors_are_all_named() -> None:
    result = suggest(
        "#ad morning with Glow",
        [],
        "instagram_reels",
        ["US"],
        {"relationship": "gifted", "sponsors": ["Glow", "Luma"]},
    )
    assert result["needed"] is True
    assert result["suggested_caption"].startswith("Ad: gifted by Glow and Luma. ")
    assert "Named Luma next to the label" in result["changes"]


def test_buried_label_is_kept_and_a_leading_one_added() -> None:
    caption = "My day #skincare " + "x" * 90 + " #ad"
    result = suggest(
        caption, [], "instagram_reels", ALL, {"relationship": "affiliate", "sponsors": []}
    )
    assert result["suggested_caption"].startswith("Ad (I earn commission on purchases): My day")
    assert result["suggested_caption"].endswith("#ad")
    assert any("only at the end" in c for c in result["changes"])


def test_denied_label_is_not_treated_as_a_disclosure_to_fix() -> None:
    result = suggest("Not sponsored, I bought this myself", [], "instagram_reels", ALL)
    assert result["needed"] is False


def test_over_long_suggestion_is_flagged() -> None:
    result = suggest(
        "x" * 2199, [], "instagram_reels", ["IN"], {"relationship": "paid", "sponsors": []}
    )
    assert result["needed"] is True
    assert "the limit is 2200" in result["note"]
