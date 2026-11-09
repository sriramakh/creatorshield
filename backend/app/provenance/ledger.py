"""Rights ledger: what the creator owns, licensed or agreed, and matching it to content.

The ledger is the creator's own record. It is never verified with the
counterparty, so coverage it provides is "you have recorded a right", not
"you are cleared".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PlatformConnection, RightsRecord

KINDS = {
    "own_channel": "Own channel or brand",
    "creator_permission": "Permission from a creator",
    "music_license": "Music licence or subscription",
    "footage_license": "Footage / stock / broadcast licence",
    "brand_agreement": "Paid brand agreement",
}
PLATFORM_KEYS = {"youtube_shorts": "youtube", "instagram_reels": "instagram"}


@dataclass
class LedgerEntry:
    id: str
    kind: str
    counterparty: str
    terms: list[str]
    platforms: list[str]
    client_label: str | None
    valid_from: date | None
    valid_until: date | None
    reference: str
    has_proof: bool

    def status(self, today: date) -> str:
        if self.valid_from and today < self.valid_from:
            return "not_started"
        if self.valid_until and today > self.valid_until:
            return "expired"
        return "active"

    def applies_to(self, platform: str, client_label: str | None) -> bool:
        key = PLATFORM_KEYS.get(platform, platform)
        if self.platforms and key not in self.platforms:
            return False
        # A client-scoped record must not cover an unlabelled or other client's post.
        scoped = normalise(self.client_label or "")
        if not scoped:
            return True
        return normalise(client_label or "") == scoped

    def summary(self, today: date) -> dict[str, Any]:
        return {
            "record_id": self.id,
            "kind": self.kind,
            "kind_label": KINDS.get(self.kind, self.kind),
            "counterparty": self.counterparty,
            "reference": self.reference,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "status": self.status(today),
            "has_proof": self.has_proof,
        }


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().casefold())


def normalise_handle(text: str) -> str:
    return normalise(text).lstrip("@").rstrip(".")


def load_entries(db: Session) -> list[LedgerEntry]:
    rows = db.scalars(select(RightsRecord).order_by(RightsRecord.created_at)).all()
    return [
        LedgerEntry(
            id=str(r.id),
            kind=r.kind,
            counterparty=r.counterparty,
            terms=[t for t in (r.match_terms or []) if t.strip()] or [r.counterparty],
            platforms=list(r.platforms or []),
            client_label=r.client_label,
            valid_from=r.valid_from,
            valid_until=r.valid_until,
            reference=r.reference,
            has_proof=bool(r.proof_key),
        )
        for r in rows
    ]


def connected_handles(db: Session) -> set[str]:
    """Handles of accounts connected through official OAuth (they are the creator's own)."""
    handles: set[str] = set()
    for conn in db.scalars(select(PlatformConnection)).all():
        meta = conn.account_meta or {}
        for value in (meta.get("username"), meta.get("custom_url"), conn.display_name):
            if value:
                handles.add(normalise_handle(str(value)))
    return handles


def term_matches(term: str, text: str) -> bool:
    """Whole-word, case-insensitive match. Handles (@x) match only as handles."""
    term_n = normalise(term)
    if not term_n:
        return False
    if term_n.startswith("@"):
        return normalise_handle(term_n) in {
            normalise_handle(h) for h in re.findall(r"@[\w.]{2,30}", text)
        }
    pattern = r"(?<![\w])" + re.escape(term_n) + r"(?![\w])"
    return re.search(pattern, normalise(text)) is not None


def handle_matches(term: str, handle: str) -> bool:
    return normalise_handle(term) == normalise_handle(handle)


def find_entries(
    entries: list[LedgerEntry],
    kinds: set[str],
    *,
    platform: str,
    client_label: str | None,
    text: str | None = None,
    handle: str | None = None,
) -> list[LedgerEntry]:
    out = []
    for e in entries:
        if e.kind not in kinds or not e.applies_to(platform, client_label):
            continue
        if (
            handle is not None
            and any(handle_matches(t, handle) for t in e.terms)
            or text is not None
            and any(term_matches(t, text) for t in e.terms)
        ):
            out.append(e)
    return out
