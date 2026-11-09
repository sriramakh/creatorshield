"""End-to-end processing of one analysis (runs inside the worker)."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import fields
from typing import Any

from sqlalchemy.orm import Session

from app.analysis.cross_check import build_cross_check
from app.analysis.deterministic import run_deterministic_checks
from app.analysis.merge import merge_findings
from app.analysis.prompt import build_prompt
from app.analysis.providers.base import (
    AnalysisProvider,
    MissingCredentialsError,
    ProviderError,
    ProviderResult,
)
from app.analysis.validation import validate_ai_output
from app.config import Settings, get_settings
from app.db import get_sessionmaker
from app.integrations.common import IntegrationError
from app.integrations.importer import prepare_import, prepare_owner_review
from app.media.extract import run_extraction
from app.media.probe import MediaError, MediaInfo, probe
from app.media.working_copy import make_working_copy, needs_working_copy
from app.models import Analysis
from app.policies.kb import get_kb
from app.provenance import pipeline as provenance
from app.provenance.fingerprint import file_sha256
from app.schemas import FindingDraft
from app.storage import analysis_prefix, get_storage

log = logging.getLogger(__name__)

STANDARD_LIMITATIONS = [
    "This is an automated, heuristic pre-publication review. It is not legal advice and "
    "cannot guarantee that a platform will not remove, restrict, demonetize or strike the "
    "content, or suspend the account.",
    "Platform copyright matching (Content ID, Meta Rights Manager) was not performed. "
    "Catalogue, music and web checks cover only what they can reach, so no copyright finding "
    "does not mean the content is copyright-free.",
    "Only sampled frames were reviewed visually; brief visual content between samples may "
    "be missed.",
    "Speech recognition and on-screen text recognition can contain errors, especially for "
    "Hindi, music-heavy audio and stylised fonts.",
    "Policy summaries reflect official pages as verified on the knowledge-base date; "
    "platforms update policies without notice.",
]


MODE_LIMITATIONS = {
    "caption_thumbnail": [
        "Caption + thumbnail review only: the video's frames, speech and audio were not "
        "available, so issues inside the video cannot be detected. Attach the original "
        "file to review them and cross-check the file against this post."
    ],
    "metadata_only": [
        "Metadata review only: the video's frames, speech and audio were not analysed "
        "(YouTube's API policies do not allow downloading them). Attach the original file "
        "to review them and cross-check the file against this post."
    ],
    "cross_checked": [
        "Frames, speech, on-screen text and audio were analysed from the file you supplied. "
        "The platform's copy of the video was not downloaded. The file was cross-checked "
        "against the post's official title, caption, duration and, when available, captions. "
        "A mismatch means this report may describe a different cut than the one that is live.",
    ],
}

FULL_VIDEO_MODES = {"full_video", "cross_checked"}

# YouTube help 15424877: square or vertical uploads up to 3 minutes are Shorts.
SHORTS_MAX_SECONDS = 180.0


def length_notes(platform: str, duration: float | None) -> list[str]:
    """Report notes for videos longer than the target format usually allows."""
    if duration is None or duration <= SHORTS_MAX_SECONDS + 0.5:
        return []
    minutes = f"{duration / 60:.1f} minutes"
    if platform == "youtube_shorts":
        return [
            f"This video is {minutes} long. YouTube treats only square or vertical uploads of "
            "3 minutes or less as Shorts, so it will be published as a regular video. The "
            "community-guideline, copyright and monetisation checks still apply; Shorts-specific "
            "guidance in this report may not."
        ]
    return [
        f"This video is {minutes} long. Instagram has been raising the Reels length limit "
        "gradually and it differs between accounts; check that the Reels composer accepts "
        "this length before you plan around it."
    ]


def get_provider(settings: Settings) -> AnalysisProvider:
    if settings.ai_provider == "anthropic":
        from app.analysis.providers.anthropic_provider import AnthropicProvider

        key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
        return AnthropicProvider(
            key,
            settings.anthropic_model,
            effort=settings.anthropic_effort,
            max_tokens=settings.ai_max_output_tokens,
            timeout=settings.ai_timeout_seconds,
        )
    if settings.ai_provider == "openai":
        from app.analysis.providers.openai_provider import OpenAIProvider

        key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
        return OpenAIProvider(
            key,
            settings.openai_model,
            max_tokens=settings.ai_max_output_tokens,
            timeout=settings.ai_timeout_seconds,
        )
    from app.analysis.providers.mock import MockProvider

    return MockProvider()


_MEDIA_FIELDS = {f.name for f in fields(MediaInfo)}


def _media_info(stored: dict[str, Any]) -> MediaInfo:
    return MediaInfo(**{k: v for k, v in stored.items() if k in _MEDIA_FIELDS})


def _prepare_working_copy(
    db: Session, analysis: Analysis, info: MediaInfo, settings: Settings
) -> tuple[MediaInfo, str | None]:
    """Hash the original, then re-encode a large file once. Safe to call on reruns."""
    storage = get_storage()
    assert analysis.storage_key is not None
    path = storage.local_path(analysis.storage_key)
    meta = dict(analysis.media_info or {})
    # Evidence packs and identical-file matching refer to the file the creator
    # supplied, not to the working copy.
    meta.setdefault("original_sha256", file_sha256(path))
    if meta.get("working_copy") or not needs_working_copy(info, settings):
        analysis.media_info = meta
        db.commit()
        return info, None
    _set_stage(db, analysis, "optimizing_video", 8)
    key = f"{analysis_prefix(analysis.id)}/video-work.mp4"
    try:
        make_working_copy(path, storage.local_path(key), info, settings)
        working = probe(storage.local_path(key))
    except MediaError as exc:
        storage.local_path(key).unlink(missing_ok=True)
        analysis.media_info = meta
        db.commit()
        return info, f"{exc} The video was analysed at its original size, which is slower."
    original = {k: meta.get(k) for k in ("width", "height", "video_codec", "fps", "bit_rate")}
    path.unlink(missing_ok=True)
    analysis.storage_key = key
    analysis.content_type = "video/mp4"
    analysis.media_info = {
        **working.to_dict(),
        "original_sha256": meta["original_sha256"],
        "original": original,
        "working_copy": True,
    }
    db.commit()
    return working, None


def _set_stage(db: Session, analysis: Analysis, stage: str, progress: int) -> None:
    analysis.stage = stage
    analysis.progress = progress
    db.commit()


def process_analysis(analysis_id: str, provider: AnalysisProvider | None = None) -> None:
    """RQ job entry point. Never raises for expected failures; records them instead."""
    settings = get_settings()
    db = get_sessionmaker()()
    try:
        analysis = db.get(Analysis, uuid.UUID(analysis_id))
        if analysis is None:
            log.warning("analysis %s not found (deleted?)", analysis_id)
            return
        _run(db, analysis, settings, provider)
    except Exception:
        log.exception("analysis %s failed unexpectedly", analysis_id)
        db.rollback()
        analysis = db.get(Analysis, uuid.UUID(analysis_id))
        if analysis is not None:
            analysis.status = "failed"
            analysis.stage = "failed"
            analysis.error_message = "An internal error occurred while processing this video."
            db.commit()
    finally:
        db.close()


def _run(
    db: Session, analysis: Analysis, settings: Settings, provider: AnalysisProvider | None
) -> None:
    started = time.monotonic()
    storage = get_storage()
    prefix = analysis_prefix(analysis.id)
    work_dir = storage.local_path(prefix)

    def fail(message: str) -> None:
        analysis.status, analysis.stage = "failed", "failed"
        analysis.error_message = message
        db.commit()

    analysis.status = "processing"
    analysis.error_message = None

    # ---- imported content: fetch through the official platform API ---------
    prebuilt: dict[str, Any] | None = None
    import_notes: list[str] = []
    snapshot: dict[str, Any] | None = None
    if analysis.source != "upload" and analysis.owner_supplied_media:
        _set_stage(db, analysis, "fetching_source", 6)
        try:
            snapshot = prepare_owner_review(db, analysis, settings)
        except (IntegrationError, MediaError) as exc:
            fail(exc.user_message if isinstance(exc, IntegrationError) else str(exc))
            return
        import_notes = list(analysis.limitations or [])
    elif analysis.source != "upload":
        _set_stage(db, analysis, "fetching_source", 6)
        try:
            prebuilt = prepare_import(db, analysis, settings)
        except (IntegrationError, MediaError) as exc:
            fail(exc.user_message if isinstance(exc, IntegrationError) else str(exc))
            return
        import_notes = list(analysis.limitations or [])

    if analysis.analysis_mode in FULL_VIDEO_MODES:
        if not analysis.storage_key or not storage.exists(analysis.storage_key):
            fail("The video file is no longer available.")
            return
        info = _media_info(analysis.media_info) if analysis.media_info else None
        if info is None:
            raise RuntimeError("media_info missing")
        info, copy_note = _prepare_working_copy(db, analysis, info, settings)
        if copy_note:
            import_notes.append(copy_note)
        _set_stage(db, analysis, "extracting", 10)
        try:
            extraction = run_extraction(
                storage.local_path(analysis.storage_key),
                work_dir,
                info,
                analysis.language,
                settings,
                on_stage=lambda s, p: _set_stage(db, analysis, s, p),
            )
        except MediaError as exc:
            fail(str(exc))
            return
    else:
        extraction = prebuilt or {"transcript": {"segments": []}, "frames": [], "ocr": []}
    cross_findings: list[FindingDraft] = []
    if snapshot is not None:
        report, cross_findings = build_cross_check(analysis.platform, snapshot, extraction)
        extraction["cross_check"] = report
        if snapshot.get("source_metadata"):
            extraction["source_metadata"] = snapshot["source_metadata"]
        warnings = extraction.setdefault("warnings", [])
        warnings.extend(snapshot.get("warnings") or [])
        warnings.extend(report.get("notes") or [])
    analysis.extraction = extraction
    duration = analysis.duration_seconds

    # ---- provenance: cues, catalogue fingerprint, optional paid lookups -----
    _set_stage(db, analysis, "provenance", 69)
    video_path = (
        storage.local_path(analysis.storage_key)
        if analysis.analysis_mode in FULL_VIDEO_MODES and analysis.storage_key
        else None
    )
    analysis.provenance = provenance.run_stage(
        db, analysis, extraction, video_path, work_dir, settings
    )
    _set_stage(db, analysis, "rule_checks", 72)

    drafts = run_deterministic_checks(
        analysis.platform,
        analysis.caption,
        analysis.hashtags,
        extraction,
        duration or 0.0,
        analysis_mode=analysis.analysis_mode,
        sponsorship=analysis.sponsorship,
    )
    drafts.extend(cross_findings)

    # ---- AI review ---------------------------------------------------------
    _set_stage(db, analysis, "ai_review", 78)
    kb = get_kb(str(settings.policy_kb_path))
    analysis.policy_kb_version = kb.version
    notes: list[str] = []
    result: ProviderResult | None = None
    try:
        provider = provider or get_provider(settings)
        analysis.ai_provider, analysis.ai_model = provider.name, provider.model
        payload = build_prompt(
            platform=analysis.platform,
            language=analysis.language,
            caption=analysis.caption,
            hashtags=analysis.hashtags,
            media_info=analysis.media_info or {"duration_seconds": duration},
            extraction=extraction,
            frames_dir=work_dir / "frames",
            kb=kb,
            analysis_mode=analysis.analysis_mode,
            sponsorship=analysis.sponsorship,
        )
        result = provider.analyze(payload)
        analysis.ai_status = "mock" if result.is_mock else "completed"
        analysis.ai_status_detail = None
        analysis.mock_mode = result.is_mock
        analysis.ai_model = result.model
        analysis.usage = result.usage
        analysis.ai_output = result.output.model_dump(mode="json")
    except MissingCredentialsError as exc:
        analysis.ai_status, analysis.ai_status_detail = "skipped", exc.user_message
        analysis.ai_provider = settings.ai_provider
    except ProviderError as exc:
        analysis.ai_status, analysis.ai_status_detail = "failed", exc.user_message

    if result is not None:
        ai_findings, notes = validate_ai_output(
            result.output,
            kb=kb,
            platform=analysis.platform,
            extraction=extraction,
            duration=duration,
            is_mock=result.is_mock,
        )
        drafts = merge_findings(drafts, ai_findings)
        analysis.summary = result.output.summary
        analysis.context_assessment = result.output.context_assessment
        notes.extend(f"Not assessed: {u}" for u in result.output.unassessable[:8])
    else:
        analysis.summary = (
            "AI review did not run, so only rule-based checks are shown. "
            + (analysis.ai_status_detail or "")
        ).strip()

    # ---- persist -------------------------------------------------------------
    _set_stage(db, analysis, "finalizing", 95)
    # Provenance findings are added after the AI merge: they come from lookups
    # and the rights ledger, not from the content the model saw.
    provenance_findings, analysis.provenance = provenance.derive(db, analysis, extraction)
    drafts.extend(provenance_findings)
    provenance.persist(db, analysis, drafts)

    limitations = list(MODE_LIMITATIONS.get(analysis.analysis_mode, []))
    limitations.extend(length_notes(analysis.platform, analysis.duration_seconds))
    limitations.extend(STANDARD_LIMITATIONS)
    limitations.extend(import_notes)
    limitations.extend(extraction.get("warnings", []))
    limitations.extend((analysis.provenance or {}).get("warnings", []))
    transcript: dict[str, Any] = extraction.get("transcript") or {}
    prob = transcript.get("language_probability")
    if prob is not None and prob < 0.5:
        limitations.append("Speech-language detection confidence was low; transcript may be poor.")
    if analysis.ai_status != "completed":
        limitations.insert(
            0,
            "AI review was not performed for this analysis "
            f"({analysis.ai_status}); findings are rule-based only.",
        )
    limitations.extend(notes)
    cross_check = extraction.get("cross_check") or {}
    if cross_check.get("file_matches_post") == "no":
        limitations.insert(
            0,
            "The supplied file does not match the published post (length or speech differ). "
            "This report describes the supplied file, which may not be the cut that is live.",
        )
    analysis.limitations = limitations

    analysis.status, analysis.stage, analysis.progress = "completed", "completed", 100
    if analysis.usage is None:
        analysis.usage = {}
    analysis.usage = {**analysis.usage, "processing_seconds": round(time.monotonic() - started, 1)}
    db.commit()

    if settings.delete_media_after_analysis:
        storage.delete_prefix(prefix)
        analysis.media_deleted = True
        analysis.storage_key = None
        db.commit()
    log.info(
        "analysis %s completed: %d findings, risk=%s", analysis.id, len(drafts), analysis.risk_level
    )
