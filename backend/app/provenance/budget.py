"""Monthly budget and response cache for paid lookups (music ID, web image search).

Every paid call is recorded with an estimated cost. A call that would take this
month's estimated spend over ``PAID_LOOKUPS_MONTHLY_BUDGET_USD`` is not made.
Identical inputs (same audio clip or frame bytes) reuse the cached response for
``PAID_LOOKUP_CACHE_DAYS`` at no cost. Provider free tiers are ignored, so the
estimate errs high.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import PaidLookup


class BudgetExceeded(Exception):
    def __init__(self, spent: float, budget: float) -> None:
        super().__init__(
            f"Skipped: this month's paid-lookup budget (${budget:.2f}) would be exceeded "
            f"(estimated ${spent:.2f} used). Raise PAID_LOOKUPS_MONTHLY_BUDGET_USD to continue."
        )
        self.user_message = str(self)


def cache_key(service: str, provider: str, payload: bytes) -> str:
    return hashlib.sha256(service.encode() + b"|" + provider.encode() + b"|" + payload).hexdigest()


def month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def month_spend(db: Session) -> float:
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


def reserve(db: Session, est_cost: float, settings: Settings) -> None:
    spent = month_spend(db)
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
