"""Creator tools: instant caption check, brand briefs, workspace settings, insights."""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app import markets as market_registry
from app import platforms as platform_registry
from app.analysis import caption_fix, market_disclosure
from app.analysis.brief import BriefSpec, run_brief_checks
from app.analysis.deterministic import has_promo_signals, run_deterministic_checks
from app.analysis.readiness import build_readiness
from app.analysis.risk import compute_risk
from app.config import get_settings
from app.db import get_db
from app.models import AnalysisStat, BrandBrief, WorkspaceSettings
from app.policies.kb import PolicyKB, get_kb
from app.reports.sections import section_for
from app.schemas import (
    CATEGORY_LABELS,
    SEVERITY_ORDER,
    BriefOut,
    FindingDraft,
    PolicyRef,
    QuickCheckRequest,
    WorkspaceSettingsIn,
    WorkspaceSettingsOut,
)

router = APIRouter(prefix="/api")
DB = Annotated[Session, Depends(get_db)]

MAX_BRIEFS = 200
GROUP_LABELS = {
    "disclosure": "Sponsorship disclosure",
    "community": "Community guidelines",
    "claims": "Claims and monetisation",
    "rights": "Rights and reused content",
    "brief": "Brand brief",
}


# ---------------------------------------------------------------------------
# Shared helpers (also used by the upload and import routes)
# ---------------------------------------------------------------------------


def kb() -> PolicyKB:
    return get_kb(str(get_settings().policy_kb_path))


def available_platforms() -> dict[str, platform_registry.PlatformInfo]:
    return {p.id: p for p in platform_registry.available(kb().platforms_present())}


def available_markets() -> dict[str, market_registry.MarketInfo]:
    present = kb().platforms_present()
    return {m.id: m for m in market_registry.MARKETS.values() if m.kb_platform in present}


def require_platform(platform: str) -> str:
    offered = available_platforms()
    if platform not in offered:
        raise HTTPException(422, f"platform must be {platform_registry.describe(set(offered))}.")
    return platform


def workspace(db: Session) -> WorkspaceSettings:
    """The workspace settings row, created on first use."""
    row = db.get(WorkspaceSettings, 1)
    if row is None:
        defaults = [m for m in get_settings().default_markets if m in available_markets()]
        # Two first requests can arrive together (the app loads settings and config in
        # parallel), so the insert must not fail when the other one wins.
        db.execute(
            pg_insert(WorkspaceSettings)
            .values(
                id=1,
                updated_at=datetime.now(UTC),
                mode="creator",
                display_name="",
                default_platform="instagram_reels",
                default_markets=defaults or list(market_registry.DEFAULT_MARKETS),
                default_language="en",
                onboarded=False,
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )
        db.commit()
        row = db.get(WorkspaceSettings, 1)
        if row is None:  # pragma: no cover - the row exists after the upsert
            raise HTTPException(503, "Workspace settings are not available. Try again.")
    return row


def resolve_markets(db: Session, values: list[str] | None) -> list[str]:
    """Requested markets, or the workspace default. 422 on an unknown or unavailable one."""
    try:
        markets = market_registry.clean(values, default=workspace(db).default_markets)
    except market_registry.UnknownMarket as exc:
        raise HTTPException(422, str(exc)) from exc
    offered = available_markets()
    missing = [m for m in markets if m not in offered]
    if missing:
        raise HTTPException(
            422, f"No rules are loaded for: {', '.join(missing)}. Choose from {', '.join(offered)}."
        )
    return markets


def resolve_brief(
    db: Session, inline: dict[str, Any] | None, brief_id: uuid.UUID | None
) -> BriefSpec | None:
    """The brief to check against: a saved one by ID, or one supplied inline."""
    if inline is not None and brief_id is not None:
        raise HTTPException(422, "Send either brief or brief_id, not both.")
    if brief_id is not None:
        saved = db.get(BrandBrief, brief_id)
        if saved is None:
            raise HTTPException(404, "Brief not found.")
        return _spec(saved)
    if inline is None:
        return None
    try:
        spec = BriefSpec.model_validate(inline)
    except ValidationError as exc:
        raise HTTPException(422, _first_error(exc)) from exc
    return None if spec.is_empty() else spec


def _first_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    message = str(error.get("msg", "Invalid brief.")).removeprefix("Value error, ")
    field = ".".join(str(p) for p in error.get("loc", ()) if not isinstance(p, int))
    return f"{field}: {message}" if field else message


def policy_refs(rule_ids: list[str]) -> list[PolicyRef]:
    refs: list[PolicyRef] = []
    for rid in rule_ids:
        rule = kb().get(rid)
        if rule:
            refs.append(
                PolicyRef(
                    id=rule.id,
                    platform=rule.platform,
                    title=rule.title,
                    official_title=rule.official_title,
                    official_url=str(rule.official_url),
                    verified_on=rule.verified_on.isoformat(),
                )
            )
    return refs


# ---------------------------------------------------------------------------
# Instant caption check
# ---------------------------------------------------------------------------

NOT_CHECKED = [
    "Speech, on-screen text and imagery in the video",
    "Music and third-party footage",
    "The platform's paid-promotion setting and your account standing",
]


def _public(draft: FindingDraft, index: int) -> dict[str, Any]:
    data = draft.model_dump()
    data["id"] = f"q{index}"
    data["category_label"] = CATEGORY_LABELS.get(draft.category, draft.category)
    data["report_section"] = section_for(draft.category, list(draft.policy_rule_ids))
    data["policies"] = [r.model_dump() for r in policy_refs(draft.policy_rule_ids)]
    return data


@router.post("/quick-check")
def quick_check(body: QuickCheckRequest, db: DB) -> dict[str, Any]:
    """Check a caption and hashtags in milliseconds. Rule-based; nothing is stored."""
    platform = require_platform(body.platform)
    markets = resolve_markets(db, body.markets)
    brief = resolve_brief(db, body.brief, body.brief_id)
    sponsorship = body.sponsorship.model_dump()

    drafts = run_deterministic_checks(
        platform,
        body.caption,
        body.hashtags,
        {},
        0.0,
        analysis_mode="caption_only",
        sponsorship=sponsorship,
        markets=markets,
    )
    brief_check: dict[str, Any] | None = None
    if brief is not None:
        brief_check, brief_findings = run_brief_checks(
            brief, body.caption, body.hashtags, {}, analysis_mode="caption_only"
        )
        drafts.extend(brief_findings)

    # A caption check has no video, so the standing "cannot check" notes are
    # replaced by one short list of what was not looked at.
    notes = [d for d in drafts if d.finding_type == "cannot_check"]
    actionable = [d for d in drafts if d.finding_type != "cannot_check"]
    actionable.sort(key=lambda d: SEVERITY_ORDER.get(d.severity, 9))
    findings = [_public(d, i + 1) for i, d in enumerate(actionable)]
    readiness = build_readiness(
        [*findings, *[n.model_dump() for n in notes if n.category == "disclosure"]],
        ai_status=None,
        brief_check=brief_check,
        caption_only=True,
    )
    score, level = compute_risk(actionable)
    promo = has_promo_signals(body.caption, body.hashtags, {})
    return {
        "platform": platform,
        "markets": markets,
        "findings": findings,
        "readiness": readiness,
        "risk_score": score,
        "risk_level": level,
        "caption_fix": caption_fix.suggest(
            body.caption, body.hashtags, platform, markets, sponsorship, promo_detected=promo
        ),
        "market_disclosure": market_disclosure.assess(body.caption, markets),
        "brief_check": brief_check,
        "not_checked": NOT_CHECKED,
        "policy_kb_version": kb().version,
    }


# ---------------------------------------------------------------------------
# Brand briefs
# ---------------------------------------------------------------------------


def _spec(row: BrandBrief) -> BriefSpec:
    return BriefSpec.model_validate({**(row.spec or {}), "name": row.name, "brand": row.brand})


def _brief_out(row: BrandBrief) -> BriefOut:
    spec = _spec(row)
    return BriefOut(
        id=row.id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        **spec.model_dump(),
    )


def _parse_saved(body: dict[str, Any]) -> BriefSpec:
    try:
        spec = BriefSpec.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(422, _first_error(exc)) from exc
    if not spec.name:
        raise HTTPException(422, "Give the brief a name.")
    if spec.is_empty():
        raise HTTPException(422, "Add at least one requirement to the brief.")
    return spec


@router.get("/briefs")
def list_briefs(db: DB) -> list[BriefOut]:
    rows = db.scalars(select(BrandBrief).order_by(BrandBrief.updated_at.desc())).all()
    return [_brief_out(r) for r in rows]


@router.post("/briefs", status_code=status.HTTP_201_CREATED)
def create_brief(body: dict[str, Any], db: DB) -> BriefOut:
    spec = _parse_saved(body)
    if len(db.scalars(select(BrandBrief.id)).all()) >= MAX_BRIEFS:
        raise HTTPException(409, f"At most {MAX_BRIEFS} briefs can be saved. Delete one first.")
    row = BrandBrief(
        name=spec.name, brand=spec.brand, spec=spec.model_dump(exclude={"name", "brand"})
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _brief_out(row)


@router.put("/briefs/{brief_id}")
def update_brief(brief_id: uuid.UUID, body: dict[str, Any], db: DB) -> BriefOut:
    row = db.get(BrandBrief, brief_id)
    if row is None:
        raise HTTPException(404, "Brief not found.")
    spec = _parse_saved(body)
    row.name, row.brand = spec.name, spec.brand
    row.spec = spec.model_dump(exclude={"name", "brand"})
    db.commit()
    db.refresh(row)
    return _brief_out(row)


@router.delete("/briefs/{brief_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brief(brief_id: uuid.UUID, db: DB) -> Response:
    row = db.get(BrandBrief, brief_id)
    if row is None:
        raise HTTPException(404, "Brief not found.")
    # Reviews keep their own copy of the brief they were checked against.
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Workspace settings
# ---------------------------------------------------------------------------


def _settings_out(row: WorkspaceSettings) -> WorkspaceSettingsOut:
    return WorkspaceSettingsOut(
        mode="agency" if row.mode == "agency" else "creator",
        display_name=row.display_name,
        default_platform=row.default_platform,
        default_markets=list(row.default_markets or []),
        default_language=row.default_language,
        onboarded=row.onboarded,
    )


@router.get("/settings")
def get_workspace_settings(db: DB) -> WorkspaceSettingsOut:
    return _settings_out(workspace(db))


@router.put("/settings")
def update_workspace_settings(body: WorkspaceSettingsIn, db: DB) -> WorkspaceSettingsOut:
    row = workspace(db)
    if body.mode is not None:
        row.mode = body.mode
    if body.display_name is not None:
        row.display_name = body.display_name.strip()
    if body.default_platform is not None:
        row.default_platform = require_platform(body.default_platform)
    if body.default_markets is not None:
        row.default_markets = resolve_markets(db, body.default_markets)
    if body.default_language is not None:
        row.default_language = body.default_language
    if body.onboarded is not None:
        row.onboarded = body.onboarded
    db.commit()
    db.refresh(row)
    return _settings_out(row)


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------


def _summary(rows: list[AnalysisStat]) -> dict[str, Any]:
    verdicts = Counter(r.verdict for r in rows)
    scores = [r.risk_score for r in rows if r.risk_score is not None]
    return {
        "reviews": len(rows),
        "ready": verdicts.get("ready", 0),
        "review": verdicts.get("review", 0),
        "fix_first": verdicts.get("fix_first", 0),
        "ready_rate": round(verdicts.get("ready", 0) / len(rows), 3) if rows else None,
        "avg_risk_score": round(sum(scores) / len(scores), 1) if scores else None,
        "open_findings": sum(r.open_findings for r in rows),
    }


@router.get("/insights")
def insights(db: DB, days: Annotated[int, Query(ge=7, le=365)] = 30) -> dict[str, Any]:
    """Outcomes of completed reviews over a window. Holds no review content."""
    now = datetime.now(UTC)
    start = now - timedelta(days=days)
    rows = list(
        db.scalars(
            select(AnalysisStat)
            .where(AnalysisStat.created_at >= start - timedelta(days=days))
            .order_by(AnalysisStat.created_at)
        ).all()
    )
    current = [r for r in rows if r.created_at >= start]
    previous = [r for r in rows if r.created_at < start]

    per_day: dict[date, list[AnalysisStat]] = defaultdict(list)
    for r in current:
        per_day[r.created_at.astimezone(UTC).date()].append(r)
    by_day = []
    for offset in range(days, -1, -1):
        day = (now - timedelta(days=offset)).date()
        by_day.append({"date": day.isoformat(), **_summary(per_day.get(day, []))})

    group_findings: Counter[str] = Counter()
    group_reviews: Counter[str] = Counter()
    severities: Counter[str] = Counter()
    for r in current:
        for group, count in (r.group_counts or {}).items():
            group_findings[group] += int(count)
            group_reviews[group] += 1
        for severity, count in (r.severity_counts or {}).items():
            severities[severity] += int(count)

    def grouped(key: str) -> dict[Any, list[AnalysisStat]]:
        out: dict[Any, list[AnalysisStat]] = defaultdict(list)
        for r in current:
            values = getattr(r, key)
            for value in values if isinstance(values, list) else [values]:
                out[value].append(r)
        return out

    platforms = platform_registry.PLATFORMS
    by_client = [
        {"client_label": label, **_summary(items)}
        for label, items in grouped("client_label").items()
        if label
    ]
    by_client.sort(key=lambda c: (-c["reviews"], c["client_label"]))
    return {
        "window_days": days,
        "generated_at": now.isoformat(),
        "totals": _summary(current),
        "previous": _summary(previous),
        "by_day": by_day,
        "by_group": [
            {
                "group": group,
                "label": GROUP_LABELS[group],
                "findings": group_findings.get(group, 0),
                "reviews": group_reviews.get(group, 0),
            }
            for group in GROUP_LABELS
        ],
        "by_severity": {s: severities.get(s, 0) for s in SEVERITY_ORDER},
        "by_platform": [
            {
                "platform": p,
                "label": platforms[p].label if p in platforms else p,
                **_summary(items),
            }
            for p, items in sorted(grouped("platform").items())
        ],
        "by_market": [
            {
                "market": m,
                "label": market_registry.MARKETS[m].label,
                "reviews": len(items),
            }
            for m, items in grouped("markets").items()
            if m in market_registry.MARKETS
        ],
        "by_client": by_client[:20],
        "stats_retention_days": get_settings().usage_stats_retention_days,
    }
