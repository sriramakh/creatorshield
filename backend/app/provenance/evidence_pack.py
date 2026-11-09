"""Claim-ready evidence pack: one zip a creator can attach to a dispute or send to a lawyer.

Contents: the report, a manifest (file hash, checks run, matches found), the
rights-ledger records the report relies on with their proof files, and a
dispute-note draft to edit. It does not assert a legal position: the draft is
marked as such and every claim in it comes from the creator's own ledger.
"""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import Analysis, RightsRecord
from app.storage import get_storage

README = """CreatorShield evidence pack
===========================

report.html          The full pre-publication review.
manifest.json        File fingerprint (SHA-256), checks that ran, matches found and
                     rights-ledger coverage, in machine-readable form.
rights/records.json  The rights-ledger entries this report relies on.
rights/<id>-proof.*  Proof files you attached to those entries.
dispute-draft.txt    A starting point for a claim dispute or counter-notification.

The ledger is your own record. CreatorShield does not verify licences with the
other party, and this pack is not legal advice. Platforms decide claims and
disputes under their own processes and local law.
"""

_PROOF_EXT = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}


def _fmt(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    s = max(0, int(round(seconds)))
    return f"{s // 60}:{s % 60:02d}"


def dispute_draft(analysis: Analysis, lines: list[dict[str, Any]]) -> str:
    fp = (analysis.provenance or {}).get("fingerprint") or {}
    title = analysis.source_title or (analysis.caption or "").split("\n")[0] or "this video"
    covered = [line for line in lines if line["status"] in {"covered", "own"}]
    gaps = [line for line in lines if line["status"] in {"missing", "expired", "not_started"}]
    out = [
        "DRAFT - review and edit before sending. This is not legal advice.",
        "",
        f"Video: {title}",
        f"Original file SHA-256: {fp.get('sha256', 'not recorded')}",
        f"Reviewed: {analysis.created_at:%Y-%m-%d} (CreatorShield analysis {analysis.id})",
        "",
        "I am the creator of this video and have the right to use the material in it, as "
        "set out below.",
        "",
    ]
    if not covered:
        out.append("[No rights-ledger entries cover material in this video yet.]")
    for line in covered:
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


def build_zip(db: Session, analysis: Analysis, report_html: str) -> bytes:
    prov = analysis.provenance or {}
    lines: list[dict[str, Any]] = prov.get("rights") or []
    record_ids = {r["record_id"] for line in lines for r in line.get("records") or []}
    records = [db.get(RightsRecord, uuid.UUID(rid)) for rid in sorted(record_ids)]
    storage = get_storage()
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
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
        "catalogue": prov.get("catalogue"),
        "music": prov.get("music"),
        "web": prov.get("web"),
        "youtube": prov.get("youtube"),
        "cross_check": (analysis.extraction or {}).get("cross_check"),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", README)
        zf.writestr("report.html", report_html)
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))
        zf.writestr("dispute-draft.txt", dispute_draft(analysis, lines))
        out_records = []
        for rec in records:
            if rec is None:
                continue
            entry = {
                "id": str(rec.id),
                "kind": rec.kind,
                "counterparty": rec.counterparty,
                "match_terms": rec.match_terms,
                "platforms": rec.platforms,
                "valid_from": rec.valid_from.isoformat() if rec.valid_from else None,
                "valid_until": rec.valid_until.isoformat() if rec.valid_until else None,
                "reference": rec.reference,
                "notes": rec.notes,
                "proof_file": None,
            }
            if rec.proof_key and storage.exists(rec.proof_key):
                name = f"rights/{rec.id}-proof{_PROOF_EXT.get(rec.proof_content_type or '', '')}"
                zf.write(storage.local_path(rec.proof_key), name)
                entry["proof_file"] = name
            out_records.append(entry)
        zf.writestr("rights/records.json", json.dumps(out_records, indent=2))
    return buf.getvalue()
