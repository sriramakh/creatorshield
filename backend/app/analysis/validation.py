"""Server-side validation of AI output.

Nothing the model returns is trusted blindly:
* policy rule IDs must exist in the KB *and* apply to the target platform;
  anything else is removed and noted (never shown as a citation).
* evidence ref_ids must refer to items that exist in this analysis; an
  "observed_evidence" finding left without valid evidence is downgraded to
  "suspected_violation".
* timestamps are clamped to the video duration; if absent they are derived
  from the cited evidence.
* free text is length-limited.
"""

from __future__ import annotations

import re
from typing import Any

from app.policies.kb import PolicyKB
from app.schemas import AIAnalysisOutput, FindingDraft

MAX_TITLE = 200
MAX_TEXT = 2000


def build_evidence_index(
    extraction: dict[str, Any],
) -> dict[str, tuple[float | None, float | None]]:
    """Map every referencable evidence ID to its (start, end) time."""
    index: dict[str, tuple[float | None, float | None]] = {
        "CAPTION": (None, None),
        "HASHTAGS": (None, None),
        "METADATA": (None, None),
    }
    for s in (extraction.get("transcript") or {}).get("segments", []):
        index[s["id"]] = (s["start"], s["end"])
    for f in extraction.get("frames") or []:
        # A thumbnail is not a moment in the video, so it carries no timestamp.
        ts = None if f.get("reason") == "thumbnail" else f["timestamp"]
        index[f["id"]] = (ts, ts)
    for o in extraction.get("ocr") or []:
        index[o["id"]] = (o["timestamp"], o["timestamp"])
    return index


def _clamp(value: float | None, duration: float | None) -> float | None:
    if value is None or value != value:  # None or NaN
        return None
    if duration is None:
        # Unknown duration (e.g. thumbnail-only review): timestamps cannot be verified.
        return None
    return round(min(max(value, 0.0), duration), 2)


def _trim(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


_REF_NORMALISE = re.compile(r"\s+")


def validate_ai_output(
    output: AIAnalysisOutput,
    *,
    kb: PolicyKB,
    platform: str,
    extraction: dict[str, Any],
    duration: float | None,
    is_mock: bool = False,
) -> tuple[list[FindingDraft], list[str]]:
    """Return (validated findings, analysis-level notes)."""
    evidence_index = build_evidence_index(extraction)
    notes: list[str] = []
    findings: list[FindingDraft] = []

    for f in output.findings:
        vnotes: list[str] = []

        rule_ids: list[str] = []
        for rid in f.policy_rule_ids:
            rid = rid.strip().upper()
            if kb.applies(rid, platform):
                if rid not in rule_ids:
                    rule_ids.append(rid)
            elif kb.get(rid):
                vnotes.append(f"Removed citation {rid}: it does not apply to this platform.")
            else:
                vnotes.append(f"Removed unverified citation '{_trim(rid, 40)}' (not in KB).")

        evidence: list[dict[str, Any]] = []
        times: list[tuple[float | None, float | None]] = []
        for ev in f.evidence:
            ref = _REF_NORMALISE.sub("", ev.ref_id).upper()
            if ref in evidence_index:
                start, end = evidence_index[ref]
                times.append((start, end))
                evidence.append(
                    {
                        "source": ev.source,
                        "ref_id": ref,
                        "detail": _trim(ev.detail, 400),
                        "timestamp": start,
                    }
                )
            else:
                vnotes.append(f"Dropped evidence reference '{_trim(ev.ref_id, 20)}' (not found).")

        finding_type: str = f.finding_type
        if finding_type == "observed_evidence" and not evidence:
            finding_type = "suspected_violation"
            vnotes.append("Downgraded to 'suspected': no verifiable evidence reference.")

        start_s = _clamp(f.start_seconds, duration)
        end_s = _clamp(f.end_seconds, duration)
        if start_s is None:
            starts = [t[0] for t in times if t[0] is not None]
            ends = [t[1] for t in times if t[1] is not None]
            if starts:
                start_s, end_s = min(starts), max(ends) if ends else None
        if start_s is not None and end_s is not None and end_s < start_s:
            start_s, end_s = end_s, start_s

        # "Suspected" and licensing findings are judgements by definition, so a
        # person must confirm them regardless of what the model says.
        requires_review = (
            f.requires_human_review
            or not rule_ids
            or f.confidence == "low"
            or finding_type in ("suspected_violation", "licensing_uncertainty")
        )
        if not rule_ids:
            vnotes.append("No verified policy reference - treat as advisory; human review needed.")

        findings.append(
            FindingDraft(
                source="ai",
                category=f.category,
                finding_type=finding_type,  # type: ignore[arg-type]
                severity=f.severity,
                confidence=f.confidence,
                title=_trim(
                    ("[MOCK] " if is_mock and not f.title.startswith("[MOCK]") else "") + f.title,
                    MAX_TITLE,
                ),
                explanation=_trim(f.explanation, MAX_TEXT),
                suggested_action=_trim(f.suggested_action, MAX_TEXT),
                start_seconds=start_s,
                end_seconds=end_s,
                evidence=evidence,
                policy_rule_ids=rule_ids,
                context_exception=_trim(f.context_exception, MAX_TEXT)
                if f.context_exception
                else None,
                requires_human_review=requires_review,
                validation_notes=vnotes,
            )
        )

    if output.embedded_instructions_detected:
        notes.append(
            "The uploaded content appears to contain text addressed to an AI reviewer. It was "
            "treated as data and did not change the review instructions."
        )
    removed = sum(1 for f in findings for n in f.validation_notes if n.startswith("Removed"))
    if removed:
        notes.append(f"{removed} unverified or inapplicable policy citation(s) were removed.")
    return findings, notes
