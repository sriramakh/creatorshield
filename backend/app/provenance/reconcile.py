"""Reconcile rule-based and AI findings with provenance results and the rights ledger.

The AI review sees the same frames as the provenance checks, so it often reports
the same handle, broadcaster or brand. Two outcomes, recomputed on every rebuild
(so they follow ledger changes):

* supporting record - a possible ledger match is noted for human review;
                      free-text findings remain counted.
* duplicate - a provenance finding already reports the same gap (with the
              ledger-aware fix). The duplicate stays visible, muted, and does not
              count twice.
"""

from __future__ import annotations

import re
from typing import Any

from app.provenance.ledger import term_matches
from app.schemas import SEVERITY_ORDER, FindingDraft

AREA_CATEGORIES = {
    "handle": {"originality", "licensing"},
    "broadcaster": {"licensing", "originality"},
    "brand": {"disclosure"},
    "music": {"licensing"},
    "web": {"licensing", "originality"},
}
AREA_TITLES = {
    "handle": "Another account's handle is on screen",
    "broadcaster": "Third-party branding on screen",
    "brand": "Paid agreement with",
    "music": "Identified music",
    "web": "Frames ",
}
SOURCE_NAMES = {"ai": "AI review", "combined": "AI review", "deterministic": "rule-based check"}
_OPEN = {"missing", "expired", "not_started"}
_QUOTED = re.compile(r"“([^”]+)”")
_FRAME = re.compile(r"^Frame (F\d+)")


def _terms_and_refs(
    line: dict[str, Any], cues: dict[str, Any], ocr_frames: dict[str, str]
) -> tuple[set[str], set[str]]:
    subject = str(line.get("subject") or "")
    terms: set[str] = set()
    refs: set[str] = set()
    area = line["area"]
    if area == "handle":
        terms |= {subject.casefold(), subject.lstrip("@").casefold()}
        items = [h for h in cues.get("handles") or [] if h["handle"] == subject]
    elif area == "broadcaster":
        terms.add(subject.casefold())
        items = [b for b in cues.get("broadcasters") or [] if b["name"] == subject]
    else:
        items = []
    for item in items:
        refs.add(item["ref_id"])
        if item["ref_id"] in ocr_frames:
            refs.add(ocr_frames[item["ref_id"]])
    if area == "brand":
        terms.add(subject.casefold())
        terms |= {r["counterparty"].casefold() for r in line.get("records") or []}
    if area == "music":
        terms |= {m.casefold() for m in _QUOTED.findall(subject)}
    if area == "web":
        match = _FRAME.match(subject)
        if match:
            refs.add(match.group(1))
    return {t for t in terms if len(t) >= 4}, refs


def _hit(f: FindingDraft, area: str, terms: set[str], refs: set[str]) -> bool:
    if f.category not in AREA_CATEGORIES.get(area, set()):
        return False
    if refs & {str(e.get("ref_id")) for e in f.evidence}:
        return True
    text = " ".join([f.title, f.explanation, *(str(e.get("detail") or "") for e in f.evidence)])
    return any(term_matches(t, text) for t in terms)


def _record_text(line: dict[str, Any]) -> str:
    recs = line.get("records") or []
    if not recs:
        return "your own account" if line["status"] == "own" else "your rights ledger"
    r = recs[0]
    ref = f", ref. {r['reference']}" if r.get("reference") else ""
    return f"{r['kind_label'].lower()} with {r['counterparty']}{ref}"


def reconcile(
    drafts: list[FindingDraft],
    lines: list[dict[str, Any]],
    provenance: dict[str, Any],
    extraction: dict[str, Any],
) -> None:
    """Set rights_status / rights_note on non-provenance findings, in place."""
    cues = provenance.get("cues") or {}
    ocr_frames = {o["id"]: o.get("frame_id") for o in extraction.get("ocr") or []}
    prepared = [
        (line, *_terms_and_refs(line, cues, ocr_frames))
        for line in lines
        if line["area"] in AREA_CATEGORIES
    ]
    own = [f for f in drafts if f.source == "provenance"]
    for f in drafts:
        if f.source == "provenance":
            continue
        f.rights_status, f.rights_note = None, None
        f.validation_notes = [
            n for n in f.validation_notes if not n.startswith("Provenance check:")
        ]
        if f.finding_type == "cannot_check":
            continue
        matched = [(line, t, r) for line, t, r in prepared if _hit(f, line["area"], t, r)]
        if not matched:
            continue
        open_lines = [m for m in matched if m[0]["status"] in _OPEN]
        closed = [m for m in matched if m[0]["status"] in {"covered", "own"}]
        if closed and not open_lines:
            line = closed[0][0]
            if f.category != "licensing":
                # A licence or permission answers the rights question, not originality
                # or disclosure: those findings keep counting.
                f.rights_note = (
                    f"{line['subject']} is recorded as {_record_text(line)}. That covers "
                    "the rights, not this issue, so it still counts."
                )
                continue
            # Free-text findings may contain several concerns. A shared frame or
            # counterparty name cannot prove that the entire finding is covered.
            f.requires_human_review = True
            f.rights_note = (
                f"Potential supporting record: {line['subject']} "
                f"is recorded as {_record_text(line)}. "
                "Confirm that it covers every concern and intended use; this finding still counts."
            )
            continue
        for line, _, _ in open_lines:
            target = next(
                (
                    p
                    for p in own
                    if AREA_TITLES[line["area"]] in p.title
                    and (line["area"] not in {"brand", "music"} or line["subject"] in p.title)
                ),
                None,
            )
            if target is None or target.rights_status is not None:
                continue
            if SEVERITY_ORDER[f.severity] < SEVERITY_ORDER[target.severity]:
                # The other review rated it more severe: count that one instead.
                target.rights_status = "duplicate"
                target.rights_note = (
                    f"Same issue as “{f.title}” ({SOURCE_NAMES.get(f.source, f.source)}), "
                    "which is counted instead."
                )
                f.validation_notes.append(f"Provenance check: {target.title}")
                continue  # it may absorb several provenance findings
            f.rights_status = "duplicate"
            f.rights_note = (
                f"Same issue as the provenance finding “{target.title}”, which is counted instead."
            )
            note = f"Also flagged by the {SOURCE_NAMES.get(f.source, f.source)}: {f.title}"
            if note not in target.validation_notes:
                target.validation_notes.append(note)
            break
