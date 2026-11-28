"""Claim-ready evidence pack: one zip a creator can attach to a dispute or send to a lawyer.

Contents: the report, a manifest (file hash, checks run, matches found), the
rights-ledger records the pack relies on with their proof files, and a
dispute-note draft to edit. It does not assert a legal position: the draft is
marked as such and every claim in it comes from the creator's own ledger.

The pack leaves the workspace, so it carries only what the claim needs:

* coverage is re-derived from the current ledger before the pack is built, and a
  coverage line is only relied on when every record behind it still exists and is
  active today;
* only the records behind covered / own lines are attached (not records that are
  merely mentioned, expired or not yet valid);
* other clients of the workspace are never named: catalogue matches with another
  owner are reduced to "another client in this workspace".
"""

from __future__ import annotations

import copy
import io
import json
import re
import uuid
import zipfile
from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import Analysis, RightsRecord
from app.provenance.ledger import normalise
from app.storage import get_storage

README = """CreatorShield evidence pack
===========================

report.html          The full pre-publication review.
manifest.json        File fingerprint (SHA-256), checks that ran, matches found and
                     rights-ledger coverage, in machine-readable form.
rights/records.json  The rights-ledger entries this pack relies on (active records
                     behind covered or own-content lines).
rights/<id>-proof.*  Proof files you attached to those entries.
dispute-draft.txt    A starting point for a claim dispute or counter-notification.

The ledger is your own record. CreatorShield does not verify licences with the
other party, and this pack is not legal advice. Platforms decide claims and
disputes under their own processes and local law. Other clients of this
workspace are not named in this pack.
"""

OTHER_CLIENT = "another client in this workspace"
OTHER_TITLE = "an earlier video"
RELIED_ON = {"covered", "own"}
GAPS = {"missing", "expired", "not_started"}
_PROOF_EXT = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}


def _fmt(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    s = max(0, int(round(seconds)))
    return f"{s // 60}:{s % 60:02d}"


# --------------------------------------------------------------------------- redaction


def _own_label(analysis: Analysis, prov: dict[str, Any]) -> str:
    return normalise(
        str((prov.get("catalogue") or {}).get("owner_label") or analysis.client_label or "")
    )


def other_client_terms(analysis: Analysis) -> list[str]:
    """Owner labels and titles of catalogue matches that belong to someone else."""
    prov = analysis.provenance or {}
    mine = _own_label(analysis, prov)
    terms: set[str] = set()
    for m in (prov.get("catalogue") or {}).get("matches") or []:
        if m.get("same_owner") or (mine and normalise(str(m.get("owner_label") or "")) == mine):
            continue
        for value in (m.get("owner_label"), m.get("title")):
            if value and len(str(value).strip()) >= 2:
                terms.add(str(value).strip())
    return sorted(terms, key=len, reverse=True)  # longest first: titles before labels


def _replacer(analysis: Analysis) -> Any:
    prov = analysis.provenance or {}
    mapping: dict[str, str] = {}
    for m in (prov.get("catalogue") or {}).get("matches") or []:
        if m.get("owner_label"):
            mapping.setdefault(str(m["owner_label"]).strip().casefold(), OTHER_CLIENT)
        if m.get("title"):
            mapping[str(m["title"]).strip().casefold()] = OTHER_TITLE
    terms = other_client_terms(analysis)
    if not terms:
        return lambda text: text
    pattern = re.compile(
        "|".join(r"(?<!\w)" + re.escape(t) + r"(?!\w)" for t in terms), re.IGNORECASE
    )

    def sub(text: str) -> str:
        return pattern.sub(lambda mo: mapping.get(mo.group(0).casefold(), OTHER_CLIENT), text)

    return sub


def _scrub(value: Any, sub: Any) -> Any:
    if isinstance(value, str):
        return sub(value)
    if isinstance(value, list):
        return [_scrub(v, sub) for v in value]
    if isinstance(value, dict):
        return {k: _scrub(v, sub) for k, v in value.items()}
    return value


def _redact_catalogue(analysis: Analysis, block: dict[str, Any] | None) -> dict[str, Any] | None:
    if not block:
        return block
    prov = analysis.provenance or {}
    mine = _own_label(analysis, prov)
    out = copy.deepcopy(block)
    redacted = []
    for m in out.get("matches") or []:
        same = m.get("same_owner") or (mine and normalise(str(m.get("owner_label") or "")) == mine)
        if not same:
            m = {
                **m,
                "owner_label": OTHER_CLIENT,
                "title": None,
                "analysis_id": None,
                "fingerprint_id": None,
                "indexed_at": None,
            }
        redacted.append(m)
    out["matches"] = redacted
    return out


def redact_lines(analysis: Analysis, lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sub = _replacer(analysis)
    out = []
    for line in lines:
        line = _scrub(copy.deepcopy(line), sub)
        if line.get("area") == "catalogue" and line.get("match"):
            line["match"] = {**line["match"], "analysis_id": None, "fingerprint_id": None}
        out.append(line)
    return out


def redact_report_data(analysis: Analysis, data: dict[str, Any]) -> dict[str, Any]:
    """Scrub other clients' names and titles from serialised report data (JSON mode)."""
    data = _scrub(copy.deepcopy(data), _replacer(analysis))
    prov = data.get("provenance")
    if isinstance(prov, dict):
        prov["catalogue"] = _redact_catalogue(
            analysis, (analysis.provenance or {}).get("catalogue")
        )
        if isinstance(prov.get("rights"), list):
            prov["rights"] = redact_lines(analysis, (analysis.provenance or {}).get("rights") or [])
    return data


# --------------------------------------------------------------------------- reliance


def _record_ok(rec: RightsRecord | None, today: date) -> bool:
    if rec is None:
        return False
    if rec.valid_from and today < rec.valid_from:
        return False
    return not (rec.valid_until and today > rec.valid_until)


def relied_lines(
    lines: Iterable[dict[str, Any]], records: dict[str, RightsRecord | None], today: date
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split lines into (relied on, gaps). A covered / own line backed by records is
    relied on only when every one of its records still exists and is active today;
    otherwise it becomes a gap."""
    relied: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for line in lines:
        status = line.get("status")
        if status in RELIED_ON:
            recs = line.get("records") or []
            if all(_record_ok(records.get(r.get("record_id", "")), today) for r in recs):
                relied.append(line)
            else:
                gaps.append(
                    {
                        **line,
                        "status": "expired",
                        "detail": "The record behind this coverage has ended or was deleted.",
                    }
                )
        elif status in GAPS:
            gaps.append(line)
    return relied, gaps


def _load_records(db: Session, lines: Iterable[dict[str, Any]]) -> dict[str, RightsRecord | None]:
    out: dict[str, RightsRecord | None] = {}
    for line in lines:
        for r in line.get("records") or []:
            rid = str(r.get("record_id") or "")
            if rid and rid not in out:
                try:
                    out[rid] = db.get(RightsRecord, uuid.UUID(rid))
                except ValueError:
                    out[rid] = None
    return out


# --------------------------------------------------------------------------- draft + zip


def dispute_draft(
    analysis: Analysis,
    lines: list[dict[str, Any]],
    *,
    records: dict[str, RightsRecord | None] | None = None,
    today: date | None = None,
) -> str:
    """Draft text. Only coverage whose records exist and are active ``today`` is stated.

    ``records`` maps record ids to the current ledger rows; when omitted, the lines'
    own record summaries are trusted only if their stored status is "active".
    """
    today = today or date.today()
    if records is None:
        relied = [
            line
            for line in lines
            if line.get("status") in RELIED_ON
            and all(r.get("status", "active") == "active" for r in line.get("records") or [])
        ]
        gaps = [line for line in lines if line.get("status") in GAPS] + [
            {**line, "detail": "The record behind this coverage is no longer active."}
            for line in lines
            if line.get("status") in RELIED_ON and line not in relied
        ]
    else:
        relied, gaps = relied_lines(lines, records, today)
    fp = (analysis.provenance or {}).get("fingerprint") or {}
    title = analysis.source_title or (analysis.caption or "").split("\n")[0] or "this video"
    created = analysis.created_at or datetime.now(UTC)
    out = [
        "DRAFT - review and edit before sending. This is not legal advice.",
        "",
        f"Video: {title}",
        f"Original file SHA-256: {fp.get('sha256', 'not recorded')}",
        f"Reviewed: {created:%Y-%m-%d} (CreatorShield analysis {analysis.id})",
        f"Rights checked against the ledger on: {today.isoformat()}",
        "",
    ]
    if relied:
        out += [
            "I am the creator of this video and have the right to use the material in it, "
            "as set out below.",
            "",
        ]
    else:
        out.append("[No active rights-ledger entries cover material in this video yet.]")
    for line in relied:
        span = ""
        if line.get("start_seconds") is not None:
            span = f" at {_fmt(line['start_seconds'])}"
            if line.get("end_seconds") is not None:
                span += f"-{_fmt(line['end_seconds'])}"
        for rec in line.get("records") or [{}]:
            basis = (
                "is my own content"
                if line["status"] == "own"
                else f"is used under {rec.get('kind_label', 'a recorded right')} with "
                f"{rec.get('counterparty', '[party]')}"
            )
            ref = f", reference {rec['reference']}" if rec.get("reference") else ""
            start, end = rec.get("valid_from"), rec.get("valid_until")
            valid = (
                f", valid {start} to {end}"
                if start and end
                else f", valid from {start}"
                if start
                else f", valid until {end}"
                if end
                else ""
            )
            proof = " A copy is attached." if rec.get("has_proof") else ""
            out.append(f"- {line['subject']}{span} {basis}{ref}{valid}.{proof}")
    if gaps:
        out += [
            "",
            "Open items to resolve before relying on this draft (remove this section):",
            *[f"- {g['subject']}: {g['detail']}" for g in gaps],
        ]
    out += ["", "[Your name]", "[Contact details]", ""]
    return "\n".join(out)


def build_zip(
    db: Session, analysis: Analysis, report_html: str, *, today: date | None = None
) -> bytes:
    """Build the pack from ``analysis.provenance`` as it stands.

    Callers re-derive coverage first (``pipeline.ensure_current`` / ``rebuild``);
    records are re-checked here as well, so a deleted or lapsed record is never
    relied on even if the stored coverage is stale.
    """
    today = today or date.today()
    prov = analysis.provenance or {}
    raw_lines: list[dict[str, Any]] = prov.get("rights") or []
    records = _load_records(db, raw_lines)
    relied, _gaps = relied_lines(raw_lines, records, today)
    lines = redact_lines(analysis, raw_lines)
    relied_ids = [
        str(r["record_id"])
        for line in relied
        for r in line.get("records") or []
        if r.get("record_id")
    ]
    storage = get_storage()
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "rights_checked_on": today.isoformat(),
        "analysis_id": str(analysis.id),
        "platform": analysis.platform,
        "client_label": analysis.client_label,
        "source": analysis.source,
        "source_url": analysis.source_url,
        "analysis_mode": analysis.analysis_mode,
        "duration_seconds": analysis.duration_seconds,
        "file": prov.get("fingerprint"),
        "policy_kb_version": analysis.policy_kb_version,
        "risk": {"level": analysis.risk_level, "score": analysis.risk_score},
        "rights_coverage": lines,
        "catalogue": _redact_catalogue(analysis, prov.get("catalogue")),
        "music": prov.get("music"),
        "web": prov.get("web"),
        "youtube": prov.get("youtube"),
        "cross_check": _scrub((analysis.extraction or {}).get("cross_check"), _replacer(analysis)),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", README)
        zf.writestr("report.html", report_html)
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))
        zf.writestr(
            "dispute-draft.txt", dispute_draft(analysis, lines, records=records, today=today)
        )
        out_records = []
        for rid in sorted(set(relied_ids)):
            rec = records.get(rid)
            if rec is None:
                continue
            entry = {
                "id": str(rec.id),
                "kind": rec.kind,
                "counterparty": rec.counterparty,
                "platforms": rec.platforms,
                "valid_from": rec.valid_from.isoformat() if rec.valid_from else None,
                "valid_until": rec.valid_until.isoformat() if rec.valid_until else None,
                "reference": rec.reference,
                "proof_file": None,
            }
            if rec.proof_key and storage.exists(rec.proof_key):
                name = f"rights/{rec.id}-proof{_PROOF_EXT.get(rec.proof_content_type or '', '')}"
                zf.write(storage.local_path(rec.proof_key), name)
                entry["proof_file"] = name
            out_records.append(entry)
        zf.writestr("rights/records.json", json.dumps(out_records, indent=2))
    return buf.getvalue()
