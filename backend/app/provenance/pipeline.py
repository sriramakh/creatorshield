"""Provenance stage of an analysis, on-demand lookups, and rebuilding findings.

``analysis.provenance`` holds the raw facts (cues, catalogue matches and any
music / web / YouTube lookups). Findings and rights-coverage lines are derived
from those facts plus the current rights ledger by ``findings.build``, so they
can be rebuilt whenever the ledger changes or a lookup is added.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.analysis.risk import compute_risk
from app.config import Settings
from app.media.probe import MediaError
from app.models import Analysis, Finding, MediaFingerprint
from app.provenance import catalogue, cues, music, web, youtube_search
from app.provenance.common import LookupFailed
from app.provenance.findings import build
from app.provenance.fingerprint import compute_fingerprint
from app.provenance.ledger import connected_handles, load_entries
from app.provenance.reconcile import reconcile
from app.schemas import SEVERITY_ORDER, FindingDraft
from app.storage import analysis_prefix, get_storage

log = logging.getLogger(__name__)

TYPE_ORDER = {
    "observed_evidence": 0,
    "suspected_violation": 1,
    "licensing_uncertainty": 2,
    "cannot_check": 3,
}
PROMO_TITLE = "Promotional language without a visible sponsorship disclosure"


def sort_key(f: FindingDraft) -> tuple[int, int, int]:
    return (
        TYPE_ORDER.get(f.finding_type, 9) == 3,  # cannot_check last
        SEVERITY_ORDER.get(f.severity, 9),
        TYPE_ORDER.get(f.finding_type, 9),
    )


def _not_run(detail: str, provider: str) -> dict[str, Any]:
    return {"provider": provider, "status": "not_run", "detail": detail, "is_mock": False}


def run_stage(
    db: Session,
    analysis: Analysis,
    extraction: dict[str, Any],
    video: Path | None,
    work_dir: Path,
    settings: Settings,
) -> dict[str, Any]:
    """Facts gathered while the video is on disk. Never raises for expected failures."""
    ocr = extraction.get("ocr") or []
    prov: dict[str, Any] = {
        "cues": {"handles": cues.find_handles(ocr), "broadcasters": cues.find_broadcasters(ocr)},
        "warnings": [],
    }

    # ---- fingerprint + catalogue ------------------------------------------
    if video is not None and video.exists():
        try:
            fp = compute_fingerprint(
                video,
                analysis.duration_seconds or 0.0,
                settings.catalogue_max_seconds,
                settings.fpcalc_cmd,
                sha256=(analysis.media_info or {}).get("original_sha256"),
            )
            row = catalogue.save_for_analysis(db, analysis, fp, settings)
            prov["fingerprint"] = {
                "sha256": fp.sha256,
                "frames_hashed": sum(1 for h in fp.frame_hashes if h is not None),
                "audio_items": len(fp.audio_fp),
            }
            prov["catalogue"] = catalogue.find_matches(
                db, fp, row.owner_label, exclude_id=row.id, settings=settings
            )
        except MediaError as exc:
            prov["warnings"].append(f"Catalogue fingerprinting skipped: {exc}")
    else:
        prov["catalogue"] = {"entries_checked": 0, "matches": [], "skipped": True}

    # ---- paid lookups (only when configured, within budget) -----------------
    non_speech = (extraction.get("audio") or {}).get("non_speech_sound_intervals") or []
    if video is not None and settings.music_id_configured and settings.music_id_auto:
        prov["music"] = music.identify(db, video, work_dir, non_speech, settings, analysis.id)
    else:
        prov["music"] = _not_run(
            "Song identification is off."
            if not settings.music_id_configured
            else "Runs on request (automatic identification is off).",
            settings.music_id_provider,
        )

    cue_frames = _cue_frame_ids(prov, ocr)
    third_party = bool(cue_frames) or any(
        not m.get("same_owner") and not m.get("unlabelled") and m["kind"] != "same_audio"
        for m in (prov.get("catalogue") or {}).get("matches") or []
    )
    frames_dir = work_dir / "frames"
    if settings.web_detection_configured and settings.web_detection_auto and third_party:
        prov["web"] = web.search(
            db, extraction.get("frames") or [], frames_dir, cue_frames, settings, analysis.id
        )
    else:
        prov["web"] = _not_run(
            "Web image search is off."
            if not settings.web_detection_configured
            else "Runs automatically when third-party cues are found, or on request.",
            settings.web_detection_provider,
        )
    prov["youtube"] = {"status": "not_run"}
    return prov


def _cue_frame_ids(prov: dict[str, Any], ocr: list[dict[str, Any]]) -> list[str]:
    by_ocr = {o["id"]: o.get("frame_id") for o in ocr}
    ids: list[str] = []
    for item in (prov.get("cues") or {}).get("handles", []) + (prov.get("cues") or {}).get(
        "broadcasters", []
    ):
        frame = by_ocr.get(item.get("ref_id"))
        if frame and frame not in ids:
            ids.append(frame)
    return ids


def derive(
    db: Session, analysis: Analysis, extraction: dict[str, Any] | None = None
) -> tuple[list[FindingDraft], dict[str, Any]]:
    """Provenance findings + the provenance dict with fresh rights-coverage lines."""
    prov = dict(analysis.provenance or {})
    findings, lines = build(
        provenance=prov,
        platform=analysis.platform,
        client_label=analysis.client_label,
        caption=analysis.caption,
        hashtags=analysis.hashtags,
        extraction=extraction if extraction is not None else (analysis.extraction or {}),
        entries=load_entries(db),
        connected=connected_handles(db),
        today=date.today(),
    )
    prov["rights"] = lines
    prov["rights_checked_at"] = datetime.now(UTC).isoformat()
    return findings, prov


def fold_disclosure(drafts: list[FindingDraft]) -> list[FindingDraft]:
    """A recorded brand agreement makes the generic promo-language finding redundant."""
    brand = next(
        (f for f in drafts if f.source == "provenance" and f.category == "disclosure"), None
    )
    if brand is None:
        return drafts
    out = []
    for f in drafts:
        if f.source == "deterministic" and f.title == PROMO_TITLE:
            known = {e["ref_id"] for e in brand.evidence}
            brand.evidence.extend(e for e in f.evidence if e["ref_id"] not in known)
            brand.validation_notes.append(f"Includes rule-based check: {f.title}")
            continue
        out.append(f)
    return out


def persist(db: Session, analysis: Analysis, drafts: list[FindingDraft]) -> None:
    drafts = fold_disclosure(drafts)
    prov = analysis.provenance or {}
    reconcile(drafts, prov.get("rights") or [], prov, analysis.extraction or {})
    drafts.sort(key=sort_key)
    analysis.findings.clear()
    db.flush()
    for i, d in enumerate(drafts):
        analysis.findings.append(Finding(sort_order=i, **d.model_dump()))
    analysis.risk_score, analysis.risk_level = compute_risk(drafts)


def rebuild(db: Session, analysis: Analysis) -> None:
    """Re-derive provenance findings (e.g. after a ledger change or a new lookup)."""
    kept = [
        FindingDraft.model_validate(f, from_attributes=True)
        for f in analysis.findings
        if f.source != "provenance"
    ]
    found, prov = derive(db, analysis)
    analysis.provenance = prov
    persist(db, analysis, kept + found)
    db.commit()


# --------------------------------------------------------------------------- on demand


def _frames_dir(analysis: Analysis) -> Path:
    return get_storage().local_path(f"{analysis_prefix(analysis.id)}/frames")


def _video_path(analysis: Analysis) -> Path | None:
    storage = get_storage()
    if analysis.storage_key and storage.exists(analysis.storage_key):
        return storage.local_path(analysis.storage_key)
    return None


def lookup_web(db: Session, analysis: Analysis, settings: Settings) -> dict[str, Any]:
    if not settings.web_detection_configured:
        raise LookupFailed(
            "Web image search is off. Set WEB_DETECTION_PROVIDER and GOOGLE_VISION_API_KEY."
        )
    extraction = analysis.extraction or {}
    prov = dict(analysis.provenance or {})
    block = web.search(
        db,
        extraction.get("frames") or [],
        _frames_dir(analysis),
        _cue_frame_ids(prov, extraction.get("ocr") or []),
        settings,
        analysis.id,
    )
    prov["web"] = block
    analysis.provenance = prov
    rebuild(db, analysis)
    return block


def lookup_music(db: Session, analysis: Analysis, settings: Settings) -> dict[str, Any]:
    if not settings.music_id_configured:
        raise LookupFailed("Song identification is off. Set MUSIC_ID_PROVIDER and AUDD_API_TOKEN.")
    video = _video_path(analysis)
    if video is None:
        raise LookupFailed("The video file is no longer available, so its audio cannot be sent.")
    non_speech = ((analysis.extraction or {}).get("audio") or {}).get(
        "non_speech_sound_intervals"
    ) or []
    work_dir = get_storage().local_path(analysis_prefix(analysis.id))
    block = music.identify(db, video, work_dir, non_speech, settings, analysis.id)
    prov = dict(analysis.provenance or {})
    prov["music"] = block
    analysis.provenance = prov
    rebuild(db, analysis)
    return block


def lookup_youtube(
    db: Session, analysis: Analysis, query: str, settings: Settings
) -> dict[str, Any]:
    row = db.query(MediaFingerprint).filter(MediaFingerprint.analysis_id == analysis.id).first()
    if row is None:
        raise LookupFailed("This analysis has no video fingerprint to compare thumbnails with.")
    block = youtube_search.search(db, query, list(row.frame_hashes or []), row.frame_step, settings)
    prov = dict(analysis.provenance or {})
    prov["youtube"] = block
    analysis.provenance = prov
    rebuild(db, analysis)
    return block


def suggested_query(analysis: Analysis) -> str:
    extraction = analysis.extraction or {}
    return youtube_search.suggest_query(
        analysis.caption or "",
        analysis.source_title,
        (extraction.get("transcript") or {}).get("segments") or [],
    )
