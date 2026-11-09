"""ffprobe wrapper and upload validation."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ALLOWED_EXTENSIONS = {".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm"}
# ffprobe format_name values we accept (mp4/mov share the demuxer).
ALLOWED_FORMATS = {"mov,mp4,m4a,3gp,3g2,mj2", "matroska,webm"}


class MediaError(Exception):
    """Raised for invalid or unprocessable media. Message is safe to show users."""


@dataclass
class MediaInfo:
    duration_seconds: float
    width: int
    height: int
    fps: float | None
    video_codec: str
    has_audio: bool
    audio_codec: str | None
    format_name: str
    bit_rate: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_rate(rate: str | None) -> float | None:
    if not rate or rate == "0/0":
        return None
    try:
        num, _, den = rate.partition("/")
        return round(float(num) / float(den or 1), 3)
    except (ValueError, ZeroDivisionError):
        return None


def media_timeout(seconds: float, base: float = 120.0) -> float:
    """Subprocess timeout for a pass over ``seconds`` of media.

    FFmpeg decodes well above real time; allowing real time on top of ``base``
    covers slow 4K/HEVC decodes without letting a stuck process run forever.
    """
    return base + max(0.0, seconds)


def probe(path: Path, timeout: float = 30.0) -> MediaInfo:
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaError("Timed out reading the video file.") from exc
    if proc.returncode != 0:
        raise MediaError("The file could not be read as a video.")
    data = json.loads(proc.stdout or "{}")
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is None:
        raise MediaError("No video stream found in the file.")
    format_name = fmt.get("format_name", "")
    if format_name not in ALLOWED_FORMATS:
        raise MediaError(f"Unsupported container format ({format_name or 'unknown'}).")
    try:
        duration = float(fmt.get("duration") or video.get("duration") or 0)
    except ValueError:
        duration = 0.0
    if duration <= 0:
        raise MediaError("Could not determine the video duration.")
    return MediaInfo(
        duration_seconds=round(duration, 3),
        width=int(video.get("width") or 0),
        height=int(video.get("height") or 0),
        fps=_parse_rate(video.get("avg_frame_rate")),
        video_codec=str(video.get("codec_name", "unknown")),
        has_audio=audio is not None,
        audio_codec=str(audio.get("codec_name")) if audio else None,
        format_name=format_name,
        bit_rate=int(fmt["bit_rate"]) if fmt.get("bit_rate", "").isdigit() else None,
    )


def validate_extension(filename: str) -> tuple[str, str]:
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise MediaError("Only MP4, MOV and WebM videos are supported.")
    return ext, ALLOWED_EXTENSIONS[ext]


def validate_duration(info: MediaInfo, max_seconds: float, tolerance: float) -> None:
    if info.duration_seconds > max_seconds + tolerance:
        raise MediaError(
            f"Video is {info.duration_seconds:.1f}s long; the limit is {max_seconds:.0f}s."
        )
