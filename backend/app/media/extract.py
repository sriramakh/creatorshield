"""Run the full extraction stage for one video."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.config import Settings
from app.media.audio import extract_audio, sound_intervals, subtract_intervals
from app.media.frames import sample_frames
from app.media.ocr import ocr_frames
from app.media.probe import MediaInfo
from app.media.transcribe import get_transcriber

log = logging.getLogger(__name__)

StageCallback = Callable[[str, int], None]


def run_extraction(
    video: Path,
    work_dir: Path,
    info: MediaInfo,
    language: str,
    settings: Settings,
    on_stage: StageCallback | None = None,
) -> dict[str, Any]:
    """Returns a JSON-serialisable extraction dict. Frame images stay in ``work_dir``."""

    def stage(name: str, pct: int) -> None:
        if on_stage:
            on_stage(name, pct)

    result: dict[str, Any] = {"warnings": []}

    # --- audio + transcript -------------------------------------------------
    transcript: dict[str, Any] = {"provider": "none", "segments": []}
    non_speech: list[tuple[float, float]] = []
    if info.has_audio:
        stage("extracting_audio", 15)
        wav = work_dir / "audio.wav"
        extract_audio(video, wav)
        sound = sound_intervals(wav, info.duration_seconds)
        stage("transcribing", 25)
        try:
            t = get_transcriber(settings).transcribe(wav, language)
            transcript = t.to_dict()
        except Exception as exc:  # STT failure should not sink the whole analysis
            log.exception("transcription failed")
            result["warnings"].append(f"Transcription failed: {type(exc).__name__}")
        speech = [(s["start"], s["end"]) for s in transcript["segments"]]
        non_speech = subtract_intervals(sound, speech)
        result["audio"] = {
            "sound_intervals": sound,
            "non_speech_sound_intervals": non_speech,
            "non_speech_seconds": round(sum(b - a for a, b in non_speech), 2),
        }
        wav.unlink(missing_ok=True)
    else:
        result["audio"] = None
        result["warnings"].append("Video has no audio track; no transcript produced.")
    result["transcript"] = transcript

    # --- frames ---------------------------------------------------------------
    stage("sampling_frames", 55)
    frames = sample_frames(
        video,
        work_dir / "frames",
        info.duration_seconds,
        threshold=settings.scene_threshold,
        interval=settings.uniform_frame_interval_seconds,
        max_frames=settings.max_frames,
        width=settings.frame_width,
    )
    result["frames"] = [
        {"id": f.id, "timestamp": f.timestamp, "reason": f.reason, "file": f.path.name}
        for f in frames
    ]

    # --- OCR ------------------------------------------------------------------
    if settings.ocr_enabled:
        stage("reading_on_screen_text", 65)
        ocr = ocr_frames(
            [(f.id, f.timestamp, f.path) for f in frames], language, settings.tesseract_cmd
        )
        result["ocr"] = [
            {
                "id": o.id,
                "frame_id": o.frame_id,
                "timestamp": o.timestamp,
                "text": o.text,
                "mean_confidence": o.mean_confidence,
            }
            for o in ocr
        ]
    else:
        result["ocr"] = []
    return result
