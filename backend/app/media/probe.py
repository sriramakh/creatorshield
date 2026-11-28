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


# --------------------------------------------------------------------------- safe inputs
#
# FFmpeg picks a demuxer by content, and some demuxers (HLS, DASH, concat, image
# sequences...) open further files or URLs named inside the input. A playlist
# renamed to .mp4 would make ffprobe fetch URLs or read local files. Every input
# is therefore sniffed by its magic bytes, opened with that demuxer forced, and
# restricted to the local file protocol.

VIDEO_DEMUXERS = frozenset({"mov", "matroska"})
IMAGE_DEMUXERS = frozenset({"jpeg_pipe", "png_pipe", "webp_pipe"})
AUDIO_DEMUXERS = frozenset({"wav"})
_MP4_BOXES = {b"ftyp", b"moov", b"mdat", b"free", b"wide", b"skip", b"pnot", b"uuid"}


def sniff_container(path: Path) -> str | None:
    """FFmpeg demuxer name for the file's real format, from its first bytes."""
    try:
        with path.open("rb") as fh:
            head = fh.read(16)
    except OSError:
        return None
    if len(head) >= 8 and head[4:8] in _MP4_BOXES:
        return "mov"
    if head.startswith(bytes.fromhex("1a45dfa3")):
        return "matroska"
    if head.startswith(bytes.fromhex("ffd8ff")):
        return "jpeg_pipe"
    if head.startswith(bytes.fromhex("89504e470d0a1a0a")):
        return "png_pipe"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "webp_pipe"
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return "wav"
    return None


def input_args(path: Path, kinds: frozenset[str] = VIDEO_DEMUXERS) -> list[str]:
    """``-protocol_whitelist file -f <demuxer> -i <path>`` for a sniffed, allowed format."""
    fmt = sniff_container(path)
    if fmt is None or fmt not in kinds:
        raise MediaError("Unsupported or unrecognised file format.")
    return ["-protocol_whitelist", "file", "-f", fmt, "-i", str(path)]


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
    fmt = sniff_container(path)
    if fmt not in VIDEO_DEMUXERS:
        raise MediaError("Unsupported container format (only MP4, MOV and WebM files).")
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-protocol_whitelist",
                "file",
                "-f",
                str(fmt),
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaError("Timed out reading the video file.") from exc
    if proc.returncode != 0:
        raise MediaError("The file could not be read as a video.")
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise MediaError("The file could not be read as a video.") from exc
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
