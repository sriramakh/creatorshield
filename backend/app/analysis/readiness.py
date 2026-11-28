"""Publish-readiness summary: one verdict and a short checklist.

Creators ask one question: can I post this? The verdict answers it from the
findings that already exist. It never says content is safe, approved or
compliant. "ready" means these checks found nothing to fix; the checklist says
what was looked at and what was not.

Derived, never stored as truth: it is recomputed whenever findings change.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, Literal

from app.reports.sections import section_for

Verdict = Literal["ready", "review", "fix_first"]
Status = Literal["pass", "warn", "fail", "unknown"]

_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
_FULL_MODES = {"full_video", "cross_checked"}

VERDICT_HEADLINE: dict[str, str] = {
    "ready": "No issues found by these checks",
    "review": "Review before posting",
    "fix_first": "Fix before posting",
}


def _get(finding: Any, name: str, default: Any = None) -> Any:
    if isinstance(finding, dict):
        return finding.get(name, default)
    return getattr(finding, name, default)


def readiness_group(finding: Any) -> str:
    """Checklist group for a finding."""
    category = _get(finding, "category", "")
    if category == "brand_brief":
        return "brief"
    if category in {"originality", "licensing"} or _get(finding, "source") == "provenance":
        return "rights"
    section = section_for(category, list(_get(finding, "policy_rule_ids") or []))
    if section == "disclosure":
        return "disclosure"
    if section == "community":
        return "community"
    if category in {"spam_deception", "monetization"}:
        return "claims"
    return "community" if category == "context_exception" else "claims"


def is_open(finding: Any) -> bool:
    """Open findings only: not 'cannot check' notes, not covered or duplicate rights items."""
    return (
        _get(finding, "finding_type") != "cannot_check" and _get(finding, "rights_status") is None
    )


def _ids(findings: Iterable[Any]) -> list[str]:
    return [str(_get(f, "id")) for f in findings if _get(f, "id") is not None]


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _item(
    key: str, label: str, findings: Sequence[Any], clear: str, fail_from: int = 2
) -> dict[str, Any]:
    """Checklist row for one group of open findings.

    ``fail_from`` is the severity rank at which the row fails: 2 = medium (the
    default), 3 = high.
    """
    if not findings:
        return {"key": key, "label": label, "status": "pass", "detail": clear, "finding_ids": []}
    worst = max(_RANK.get(_get(f, "severity", "info"), 0) for f in findings)
    # A low-confidence finding asks for a look; it does not block on its own.
    confident = [f for f in findings if _get(f, "confidence") != "low"]
    worst_confident = max((_RANK.get(_get(f, "severity", "info"), 0) for f in confident), default=0)
    status: Status = "fail" if worst_confident >= fail_from else "warn"
    if worst == 0:
        # Informational notes only: nothing to fix.
        return {
            "key": key,
            "label": label,
            "status": "pass",
            "detail": f"{clear}; {_plural(len(findings), 'informational note')}",
            "finding_ids": _ids(findings),
        }
    names = sorted({_get(f, "severity", "info") for f in findings}, key=lambda s: -_RANK.get(s, 0))
    detail = f"{_plural(len(findings), 'open finding')} ({', '.join(names)})"
    return {
        "key": key,
        "label": label,
        "status": status,
        "detail": detail,
        "finding_ids": _ids(findings),
    }


def build_readiness(
    findings: Iterable[Any],
    *,
    ai_status: str | None,
    analysis_mode: str = "full_video",
    brief_check: dict[str, Any] | None = None,
    caption_only: bool = False,
) -> dict[str, Any]:
    """Verdict + checklist from findings and what the review could see."""
    everything = list(findings)
    open_findings = [f for f in everything if is_open(f)]
    groups: dict[str, list[Any]] = {
        k: [] for k in ("disclosure", "community", "claims", "rights", "brief")
    }
    for finding in open_findings:
        groups[readiness_group(finding)].append(finding)

    checklist: list[dict[str, Any]] = []

    # Disclosure: a missing label on promotional content is the most common fix.
    disclosure = _item(
        "disclosure",
        "Sponsorship disclosure",
        groups["disclosure"],
        "No undisclosed promotion signals found",
    )
    if disclosure["status"] == "pass":
        notes = [
            f
            for f in everything
            if _get(f, "finding_type") == "cannot_check"
            and _get(f, "category") == "disclosure"
            and _get(f, "requires_human_review")
        ]
        if notes:
            disclosure.update(
                status="warn",
                detail="Disclosure wording found. Check it is prominent in the final post",
                finding_ids=_ids(notes),
            )
    checklist.append(disclosure)

    checklist.append(
        _item(
            "community",
            "Community guidelines",
            groups["community"],
            "No community-guideline wording flags",
            fail_from=3,
        )
    )
    checklist.append(
        _item(
            "claims",
            "Claims and monetisation",
            groups["claims"],
            "No absolute claims or monetisation flags",
        )
    )
    if not caption_only:
        checklist.append(
            _item(
                "rights",
                "Rights and reused content",
                groups["rights"],
                "No third-party content signals found",
                fail_from=3,
            )
        )

    if brief_check is not None:
        total = int(brief_check.get("total", 0))
        met = int(brief_check.get("met", 0))
        unverified = int(brief_check.get("unverified", 0))
        row = _item(
            "brief",
            "Brand brief",
            groups["brief"],
            f"{met} of {total} requirements met",
        )
        if row["status"] == "pass" and unverified:
            row.update(
                status="warn",
                detail=f"{met} of {total} met; {_plural(unverified, 'requirement')} can only be "
                "checked in the video",
            )
        elif row["status"] != "pass":
            row["detail"] = f"{met} of {total} requirements met"
        checklist.append(row)

    # What the review could not see.
    if caption_only:
        checklist.append(
            {
                "key": "coverage",
                "label": "Video content",
                "status": "unknown",
                "detail": "Caption check only. Speech, on-screen text, imagery and audio "
                "were not reviewed",
                "finding_ids": [],
            }
        )
    else:
        if analysis_mode not in _FULL_MODES:
            checklist.append(
                {
                    "key": "coverage",
                    "label": "Video content",
                    "status": "warn",
                    "detail": "Only the caption, metadata or thumbnail was reviewed. Attach "
                    "the video file for a full review",
                    "finding_ids": [],
                }
            )
        ai_ok = ai_status == "completed"
        checklist.append(
            {
                "key": "ai_review",
                "label": "AI review of frames and context",
                "status": "pass" if ai_ok else "warn",
                "detail": "Completed"
                if ai_ok
                else "Did not run. Results are rule-based only"
                if ai_status in {"skipped", "failed", None}
                else "Placeholder (mock mode). Results are rule-based only",
                "finding_ids": [],
            }
        )

    blockers = sum(1 for c in checklist if c["status"] == "fail")
    warnings = sum(1 for c in checklist if c["status"] == "warn")
    needs_human = any(_get(f, "requires_human_review") for f in open_findings)
    verdict: Verdict = "fix_first" if blockers else "review" if warnings or needs_human else "ready"
    return {
        "verdict": verdict,
        "headline": VERDICT_HEADLINE[verdict],
        "blockers": blockers,
        "warnings": warnings,
        "checklist": checklist,
    }
