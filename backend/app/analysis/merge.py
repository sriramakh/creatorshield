"""Merge rule-based findings into AI findings that report the same issue.

When the AI review and a deterministic check flag the same problem (shared
evidence, or the same category over an overlapping time range), showing both
is noise. The AI finding is kept as the primary (richer explanation), and the
rule-based finding's citations and evidence are folded in, recorded as
corroboration.
"""

from __future__ import annotations

from app.schemas import SEVERITY_ORDER, FindingDraft


def _refs(f: FindingDraft) -> set[str]:
    return {e["ref_id"] for e in f.evidence if e.get("ref_id") not in ("CAPTION", "METADATA")}


def _overlaps(a: FindingDraft, b: FindingDraft) -> bool:
    if a.start_seconds is None or b.start_seconds is None:
        return False
    a_end = a.end_seconds if a.end_seconds is not None else a.start_seconds
    b_end = b.end_seconds if b.end_seconds is not None else b.start_seconds
    return a.start_seconds <= b_end + 0.5 and b.start_seconds <= a_end + 0.5


def match_score(det: FindingDraft, ai: FindingDraft) -> int:
    """0 = different issue. Higher = stronger evidence that both report the same issue.

    Same category: shared evidence or overlapping time is enough.
    Different category: require substantial evidence overlap (>= 2 refs and
    >= 2/3 of the rule-based finding's refs), so a single shared transcript
    line cannot fold e.g. a disclosure finding into a health-claim finding.
    """
    det_refs = _refs(det)
    shared = len(det_refs & _refs(ai))
    if det.category == ai.category:
        if shared or _overlaps(det, ai):
            return 100 + shared
        return 0
    if shared >= 2 and shared * 3 >= len(det_refs) * 2:
        return shared
    return 0


def corroborates(det: FindingDraft, ai: FindingDraft) -> bool:
    return match_score(det, ai) > 0


def merge_findings(deterministic: list[FindingDraft], ai: list[FindingDraft]) -> list[FindingDraft]:
    merged_ai = [f.model_copy(deep=True) for f in ai]
    remaining: list[FindingDraft] = []
    for det in deterministic:
        if det.finding_type == "cannot_check":
            remaining.append(det)
            continue
        scored = [(match_score(det, a), a) for a in merged_ai]
        best = max(scored, key=lambda s: s[0], default=(0, None))
        target = best[1] if best[0] > 0 else None
        if target is None:
            remaining.append(det)
            continue
        target.source = "combined"
        for rid in det.policy_rule_ids:
            if rid not in target.policy_rule_ids:
                target.policy_rule_ids.append(rid)
        known = {e["ref_id"] for e in target.evidence}
        target.evidence.extend(e for e in det.evidence if e["ref_id"] not in known)
        if SEVERITY_ORDER[det.severity] < SEVERITY_ORDER[target.severity]:
            target.severity = det.severity
        target.requires_human_review = target.requires_human_review or det.requires_human_review
        target.validation_notes.append(f"Corroborated by rule-based check: {det.title}")
    return merged_ai + remaining
