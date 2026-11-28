"""Rights ledger: what the creator owns, licensed or agreed, and matching it to content.

The ledger is the creator's own record. It is never verified with the
counterparty, so coverage it provides is "you have recorded a right", not
"you are cleared".
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Analysis, PlatformConnection, RightsRecord
from app.platforms import PLATFORMS

KINDS = {
    "own_channel": "Own channel or brand",
    "creator_permission": "Permission from a creator",
    "music_license": "Music licence or subscription",
    "footage_license": "Footage / stock / broadcast licence",
    "brand_agreement": "Paid brand agreement",
}
# Ledger records are scoped by platform family (a YouTube licence covers Shorts and
# long-form alike).
PLATFORM_KEYS = {p.id: p.family for p in PLATFORMS.values()}


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


def normalise_name(text: str) -> str:
    """Names compared as whole names: case, punctuation and spacing do not matter."""
    return " ".join(re.findall(r"[^\W_]+|\+", normalise(text)))


def normalise_domain(text: str) -> str:
    value = normalise(text)
    value = re.sub(r"^[a-z][a-z0-9+.-]*://", "", value)
    value = value.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    value = value.rsplit("@", 1)[-1].split(":", 1)[0].strip(".")
    return value.removeprefix("www.")


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


# --------------------------------------------------------------------------- connected accounts


@dataclass
class ConnectedAccounts:
    """Connected-account handles split by whether they belong to *this* analysis' client.

    ``own``: handles of accounts that demonstrably belong to the client and platform
    of the analysis. ``review``: handles of connected accounts that cannot be tied
    to it (another client, another platform, or an unlabelled connection in a
    workspace with several clients). They are not counted as "own".
    """

    own: set[str] = field(default_factory=set)
    review: set[str] = field(default_factory=set)
    own_channel_ids: set[str] = field(default_factory=set)


def _connection_handles(conn: PlatformConnection) -> set[str]:
    meta = conn.account_meta or {}
    values = [meta.get("username"), meta.get("custom_url")]
    if (conn.display_name or "").startswith("@"):
        values.append(conn.display_name)
    return {normalise_handle(str(v)) for v in values if v and normalise_handle(str(v))}


def client_contexts(db: Session) -> set[str]:
    """Distinct client labels used anywhere in the workspace (analyses and ledger)."""
    labels = set(db.scalars(select(Analysis.client_label).distinct()).all())
    labels |= set(db.scalars(select(RightsRecord.client_label).distinct()).all())
    return {normalise(v) for v in labels if v and normalise(v)}


def connected_accounts_for(
    db: Session,
    *,
    platform: str,
    client_label: str | None,
    connection_id: Any = None,
) -> ConnectedAccounts:
    """Which connected accounts count as the analysis' own.

    A connection is the client's own when the analysis was imported through it, or
    when posts imported through it carry the same client label. A connection with
    no client history counts only in a single-client workspace. Connections on
    another platform are listed for review, never assumed to be the same owner.
    """
    out = ConnectedAccounts()
    platform_key = PLATFORM_KEYS.get(platform, platform)
    me = normalise(client_label or "")
    contexts: set[str] | None = None
    for conn in db.scalars(select(PlatformConnection)).all():
        handles = _connection_handles(conn)
        if connection_id is not None and conn.id == connection_id:
            mine = True
        elif conn.platform != platform_key:
            mine = False
        else:
            used = {
                normalise(v)
                for v in db.scalars(
                    select(Analysis.client_label)
                    .where(Analysis.connection_id == conn.id)
                    .distinct()
                ).all()
                if v and normalise(v)
            }
            if used:
                mine = bool(me) and me in used
            else:
                if contexts is None:
                    contexts = client_contexts(db)
                mine = len(contexts) <= 1 and (not me or not contexts or me in contexts)
        if mine:
            out.own |= handles
            if conn.platform == "youtube":
                out.own_channel_ids.add(conn.external_id)
        else:
            out.review |= handles
    out.review -= out.own
    return out


def connected_handles(db: Session) -> set[str]:
    """Handles of every connected account (no client scoping). Prefer
    :func:`connected_accounts_for`, which only treats the analysis' own accounts as own."""
    handles: set[str] = set()
    for conn in db.scalars(select(PlatformConnection)).all():
        handles |= _connection_handles(conn)
    return handles


def ledger_digest(db: Session) -> str:
    """Changes whenever a record or a connected account that could affect coverage changes."""
    records = [
        [
            str(r.id),
            r.kind,
            list(r.match_terms or []),
            list(r.platforms or []),
            r.client_label,
            r.valid_from.isoformat() if r.valid_from else None,
            r.valid_until.isoformat() if r.valid_until else None,
            r.reference,
            bool(r.proof_key),
            r.counterparty,
        ]
        for r in db.scalars(select(RightsRecord)).all()
    ]
    conns = [
        [str(c.id), c.platform, c.external_id, c.display_name, c.account_meta or {}]
        for c in db.scalars(select(PlatformConnection)).all()
    ]
    blob = json.dumps([sorted(records), sorted(conns, key=lambda c: c[0])], default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


# --------------------------------------------------------------------------- matching


def term_matches(term: str, text: str) -> bool:
    """Whole-word, case-insensitive match inside free text. Handles (@x) match only as
    handles."""
    term_n = normalise(term)
    if not term_n:
        return False
    if term_n.startswith("@"):
        return normalise_handle(term_n) in {
            normalise_handle(h) for h in re.findall(r"@[\w.]{2,30}", text)
        }
    pattern = r"(?<![\w])" + re.escape(term_n) + r"(?![\w])"
    return re.search(pattern, normalise(text)) is not None


def name_matches(term: str, name: str) -> bool:
    """The term names exactly this party: "Sony" does not cover "Sony Music"."""
    term_n = normalise_name(term)
    return bool(term_n) and not normalise(term).startswith("@") and term_n == normalise_name(name)


def domain_matches(term: str, domain: str) -> bool:
    """A web page is covered only by a domain recorded on the record (or a subdomain of it)."""
    raw = normalise(term)
    if not raw or raw.startswith("@") or " " in raw:
        return False
    term_d, dom = normalise_domain(raw), normalise_domain(domain)
    return bool(term_d and dom) and (dom == term_d or dom.endswith("." + term_d))


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
    name: str | None = None,
    names: list[str] | None = None,
    domain: str | None = None,
) -> list[LedgerEntry]:
    """Records of ``kinds`` that apply to this post and match one of the given subjects.

    ``text`` is free text (whole-word search), ``handle`` an @handle, ``name`` /
    ``names`` whole names that must equal a term, ``domain`` a web domain.
    """
    out = []
    candidates = ([name] if name else []) + list(names or [])
    for e in entries:
        if e.kind not in kinds or not e.applies_to(platform, client_label):
            continue
        if (
            (handle is not None and any(handle_matches(t, handle) for t in e.terms))
            or (text is not None and any(term_matches(t, text) for t in e.terms))
            or any(name_matches(t, n) for t in e.terms for n in candidates if n)
            or (domain is not None and any(domain_matches(t, domain) for t in e.terms))
        ):
            out.append(e)
    return out
