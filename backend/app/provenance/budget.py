"""Monthly budget and response cache for paid lookups (music ID, web image search).

Every paid call is recorded with an estimated cost. A call that would take this
month's estimated spend over ``PAID_LOOKUPS_MONTHLY_BUDGET_USD`` is not made.
Identical inputs (same audio clip or frame bytes) reuse the cached response for
``PAID_LOOKUP_CACHE_DAYS`` at no cost. Provider free tiers are ignored, so the
estimate errs high.

Concurrency: the cost is *reserved* before the call, as a row in ``paid_lookups``,
while holding a database lock, so two workers cannot both pass the budget check
with the last few cents. The row is then settled (the response becomes the cache
entry), released (the provider certainly did not bill) or kept as an uncertain
charge (the client gave up, but the provider may have billed). A reservation for
the same input that is still in flight makes the second caller wait for its result
instead of paying twice.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import PaidLookup

# pg_advisory_xact_lock key for budget reservations ("CSBUDGET" as an int64).
_LOCK_ID = 0x4353_4255_4447_4554 & 0x7FFF_FFFF_FFFF_FFFF
PENDING_PREFIX = "~"  # cache_key of an in-flight reservation: "~" + sha256(key)[:63]
UNCERTAIN_PREFIX = "!"  # cache_key of a charge whose response was lost: never a cache hit
IN_FLIGHT_SECONDS = 180  # a reservation older than this is considered abandoned


class BudgetExceeded(Exception):
    def __init__(self, spent: float, budget: float) -> None:
        super().__init__(
            f"Skipped: this month's paid-lookup budget (${budget:.2f}) would be exceeded "
            f"(estimated ${spent:.2f} used). Raise PAID_LOOKUPS_MONTHLY_BUDGET_USD to continue."
        )
        self.user_message = str(self)


def cache_key(service: str, provider: str, payload: bytes) -> str:
    return hashlib.sha256(service.encode() + b"|" + provider.encode() + b"|" + payload).hexdigest()


def _pending_key(key: str) -> str:
    # Hash first: keys sharing a prefix must not share an in-flight marker.
    return PENDING_PREFIX + hashlib.sha256(key.encode()).hexdigest()[:63]


def month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def month_spend(db: Session) -> float:
    """Estimated spend this month, including reservations still in flight."""
    total = db.scalar(
        select(func.coalesce(func.sum(PaidLookup.est_cost_usd), 0.0)).where(
            PaidLookup.created_at >= month_start()
        )
    )
    return float(total or 0.0)


def cached(db: Session, key: str, settings: Settings) -> dict[str, Any] | None:
    since = datetime.now(UTC) - timedelta(days=settings.paid_lookup_cache_days)
    row = db.scalars(
        select(PaidLookup)
        .where(PaidLookup.cache_key == key, PaidLookup.created_at >= since)
        .order_by(PaidLookup.created_at.desc())
        .limit(1)
    ).first()
    return row.response if row else None


def _lock(db: Session) -> None:
    """Serialise reservations across processes for the rest of this transaction."""
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _LOCK_ID})


@dataclass
class Reservation:
    row_id: uuid.UUID
    key: str
    est_cost: float
    service: str
    provider: str
    analysis_id: uuid.UUID | None


def _in_flight(db: Session, key: str) -> bool:
    since = datetime.now(UTC) - timedelta(seconds=IN_FLIGHT_SECONDS)
    return (
        db.scalar(
            select(func.count())
            .select_from(PaidLookup)
            .where(PaidLookup.cache_key == _pending_key(key), PaidLookup.created_at >= since)
        )
        or 0
    ) > 0


def acquire(
    db: Session,
    *,
    service: str,
    provider: str,
    key: str,
    est_cost: float,
    settings: Settings,
    analysis_id: uuid.UUID | None,
    units: int = 1,
    wait_seconds: float = 60.0,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[dict[str, Any] | None, Reservation | None]:
    """Return ``(cached_response, None)`` or ``(None, reservation)``.

    Raises :class:`BudgetExceeded` when the reservation would exceed the budget.
    Commits the session (the reservation must be visible to other workers).
    """
    deadline = time.monotonic() + wait_seconds
    while True:
        _lock(db)
        hit = cached(db, key, settings)
        if hit is not None:
            db.commit()
            return hit, None
        if _in_flight(db, key) and time.monotonic() < deadline:
            db.commit()  # release the lock while the other request finishes
            sleep(0.5)
            continue
        spent = month_spend(db)
        if spent + est_cost > settings.paid_lookups_monthly_budget_usd + 1e-9:
            db.commit()
            raise BudgetExceeded(spent, settings.paid_lookups_monthly_budget_usd)
        row = PaidLookup(
            service=service,
            provider=provider,
            units=units,
            est_cost_usd=est_cost,
            cache_key=_pending_key(key),
            analysis_id=analysis_id,
            response={"pending": True},
        )
        db.add(row)
        db.flush()
        reservation = Reservation(row.id, key, est_cost, service, provider, analysis_id)
        db.commit()
        return None, reservation


def settle(db: Session, res: Reservation, response: dict[str, Any]) -> None:
    """The call succeeded: the reservation becomes the charge and the cache entry."""
    row = db.get(PaidLookup, res.row_id)
    if row is None:  # removed meanwhile (e.g. its analysis was deleted): record anew
        row = PaidLookup(
            service=res.service,
            provider=res.provider,
            est_cost_usd=res.est_cost,
            analysis_id=res.analysis_id,
        )
        db.add(row)
    row.cache_key = res.key
    row.response = response
    db.commit()


def release(db: Session, res: Reservation) -> None:
    """The provider did not bill (no request was sent, or it was refused)."""
    db.execute(delete(PaidLookup).where(PaidLookup.id == res.row_id))
    db.commit()


def mark_uncertain(db: Session, res: Reservation, reason: str) -> None:
    """The provider may have billed (timeout after sending, unreadable answer):
    keep the charge, but never serve it as a cached answer."""
    row = db.get(PaidLookup, res.row_id)
    if row is not None:
        row.cache_key = UNCERTAIN_PREFIX + uuid.uuid4().hex
        row.response = {"uncertain_charge": True, "reason": reason[:200]}
        db.commit()


def reserve(db: Session, est_cost: float, settings: Settings) -> None:
    """Budget check without a reservation (kept for callers that only need a check)."""
    _lock(db)
    spent = month_spend(db)
    db.commit()
    if spent + est_cost > settings.paid_lookups_monthly_budget_usd + 1e-9:
        raise BudgetExceeded(spent, settings.paid_lookups_monthly_budget_usd)


def record(
    db: Session,
    *,
    service: str,
    provider: str,
    key: str,
    est_cost: float,
    response: dict[str, Any],
    analysis_id: uuid.UUID | None,
    units: int = 1,
) -> None:
    db.add(
        PaidLookup(
            service=service,
            provider=provider,
            units=units,
            est_cost_usd=est_cost,
            cache_key=key,
            analysis_id=analysis_id,
            response=response,
        )
    )
    db.commit()


def status(db: Session, settings: Settings) -> dict[str, Any]:
    rows = db.execute(
        select(PaidLookup.service, func.count(), func.sum(PaidLookup.est_cost_usd))
        .where(PaidLookup.created_at >= month_start())
        .group_by(PaidLookup.service)
    ).all()
    by_service = {s: {"calls": int(n), "est_cost_usd": round(float(c or 0), 4)} for s, n, c in rows}
    spent = sum(v["est_cost_usd"] for v in by_service.values())
    return {
        "month_start": month_start().date().isoformat(),
        "budget_usd": settings.paid_lookups_monthly_budget_usd,
        "spent_usd": round(spent, 4),
        "remaining_usd": round(max(0.0, settings.paid_lookups_monthly_budget_usd - spent), 4),
        "by_service": by_service,
    }
