"""Suggest a caption whose disclosure works in every selected market.

When a post looks commercial (promotion wording, a declared relationship or a
half-hearted label) and the caption does not open with a label each selected
regulator treats as clear, this proposes the smallest edit that would: put
"Ad" first, name the sponsors, and keep everything the creator wrote.

"Ad" is used because it is the one label ASCI, the FTC and the ASA / CMA all
describe as clear. The suggestion is a starting point for the creator to edit,
never a clearance: the platform's paid-partnership setting and the on-screen
disclosure still need doing, and those cannot be seen from a caption.
"""

from __future__ import annotations

import re
from typing import Any

from app.analysis.market_disclosure import UNIVERSAL_LABEL, assess, find_labels
from app.analysis.textnorm import normalise
from app.markets import MARKETS, names
from app.platforms import PLATFORMS

# Published caption limits. A suggestion that would exceed one is flagged.
CAPTION_LIMITS: dict[str, int] = {"instagram": 2200, "youtube": 5000}

_RELATION_PHRASE: dict[str, str] = {
    "paid": "paid partnership with {names}",
    "gifted": "gifted by {names}",
    "affiliate": "I earn commission from {names}",
    "employment": "I work with {names}",
    "other": "in partnership with {names}",
    "unknown": "in partnership with {names}",
}
_RELATION_ALONE: dict[str, str] = {
    "gifted": "gifted product",
    "affiliate": "I earn commission on purchases",
}

# A label written on its own at the very start: "Ad:", "#ad", "AD |", "Sponsored -".
_LEADING_LABEL = re.compile(r"^\s*#?[A-Za-z][\w ]{0,24}?\s*[:|–—-]\s*")


def _join(values: list[str]) -> str:
    if len(values) <= 1:
        return "".join(values)
    return ", ".join(values[:-1]) + " and " + values[-1]


def _named(text: str, name: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, re.IGNORECASE))


def suggest(
    caption: str,
    hashtags: list[str],
    platform: str,
    markets: list[str],
    sponsorship: dict[str, Any] | None = None,
    promo_detected: bool = False,
) -> dict[str, Any]:
    """A caption with a clear opening disclosure, or ``needed: False`` when none is called for."""
    context = sponsorship or {}
    relationship = str(context.get("relationship") or "unknown")
    sponsors = [normalise(s).strip() for s in context.get("sponsors") or [] if str(s).strip()]
    text = normalise(caption).strip()
    labels = find_labels(text)
    asserted = [f for f in labels if not f.denied]
    declared = relationship not in {"unknown", "none"}
    commercial = declared or promo_detected or bool(asserted) or bool(sponsors)

    result: dict[str, Any] = {
        "needed": False,
        "suggested_caption": caption,
        "suggested_hashtags": hashtags,
        "label": None,
        "changes": [],
        "note": "",
        "markets": {m: v["status"] for m, v in assess(text, markets)["by_market"].items()},
    }
    if not commercial:
        result["note"] = (
            "No promotion wording, sponsor or commercial relationship was found, so no "
            "disclosure was added. If you received payment, a free product or commission, "
            "say so and check again."
        )
        return result

    opening_text = text[:160]
    all_clear = all(status == "clear" for status in result["markets"].values())
    sponsors_named = all(_named(opening_text, s) for s in sponsors)
    if all_clear and sponsors_named:
        result["note"] = (
            f"The caption opens with a label that is clear for {names(markets)}. Also turn on "
            f"{PLATFORMS[platform].disclosure_setting} and show the disclosure in the video."
        )
        return result

    changes: list[str] = []
    body = text
    # Drop a leading label that is being replaced, so the caption does not read "Ad: Collab: ...".
    lead = _LEADING_LABEL.match(body)
    if lead and labels and labels[0].offset < lead.end() and not labels[0].denied:
        old = body[: lead.end()].strip()
        body = body[lead.end() :].lstrip()
        if not all(labels[0].clear_in(m) for m in markets):
            where = _join([MARKETS[m].regulator for m in markets if not labels[0].clear_in(m)])
            changes.append(f'Replaced "{old}", which {where} guidance does not treat as clear')

    unnamed = [s for s in sponsors if not _named(opening_text, s)] if sponsors else []
    if sponsors and not unnamed:
        # The opening already names every sponsor; only the label is missing.
        prefix = f"{UNIVERSAL_LABEL}: "
    elif sponsors:
        phrase = _RELATION_PHRASE.get(relationship, _RELATION_PHRASE["unknown"]).format(
            names=_join(sponsors)
        )
        prefix = f"{UNIVERSAL_LABEL}: {phrase}. "
        if unnamed:
            changes.append(f"Named {_join(unnamed)} next to the label")
    else:
        alone = _RELATION_ALONE.get(relationship)
        prefix = f"{UNIVERSAL_LABEL} ({alone}): " if alone else f"{UNIVERSAL_LABEL}: "
    changes.insert(0, f'Opened the caption with "{UNIVERSAL_LABEL}"')

    buried = [f for f in asserted if not f.opening and all(f.clear_in(m) for m in markets)]
    if buried:
        changes.append(
            f'Kept "{buried[0].text}" where it was; a label only at the end is easy to miss'
        )

    suggested = (prefix + body).strip()
    limit = CAPTION_LIMITS.get(PLATFORMS[platform].family)
    note = (
        f'"{UNIVERSAL_LABEL}" is the label {_join([MARKETS[m].regulator for m in markets])} '
        f"guidance describes as clear. Edit the wording so it is true for your arrangement, "
        f"turn on {PLATFORMS[platform].disclosure_setting}, and show the disclosure in the "
        "video as well. A suggestion to review, not legal advice."
    )
    if limit and len(suggested) > limit:
        note += f" The suggestion is {len(suggested)} characters; the limit is {limit}."
    result.update(
        needed=True,
        suggested_caption=suggested,
        label=UNIVERSAL_LABEL,
        changes=changes,
        note=note,
    )
    return result
