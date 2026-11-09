"""Smaller working copy of a large upload.

Analysis never needs more than 1080p: frames are scaled to ``frame_width`` and
fingerprints to a 17x16 grid. A 4K or high-bitrate file is re-encoded once, so
scene detection, frame sampling, audio and fingerprinting each read a small file
instead of decoding 4K again. The copy also plays in every browser (iPhone HEVC
.mov files do not play in Chrome) and drops container metadata such as GPS
location. The original's SHA-256 is recorded before it is deleted.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.config import Settings
from app.media.probe import MediaError, MediaInfo, media_timeout


def needs_working_copy(info: MediaInfo, settings: Settings) -> bool:
    short_side = min(info.width, info.height) if info.width and info.height else 0
    if settings.working_copy_max_short_side and short_side > settings.working_copy_max_short_side:
        return True
    limit = settings.working_copy_max_bitrate_kbps
    return bool(limit and info.bit_rate and info.bit_rate > limit * 1000)


def make_working_copy(src: Path, dst: Path, info: MediaInfo, settings: Settings) -> None:
    """H.264/AAC MP4, short side <= the configured maximum, <= 30 fps."""
    side = settings.working_copy_max_short_side or 100_000
    # Applied after autorotation, so iw/ih are the displayed (upright) dimensions.
    scale = f"scale=w='if(lte(iw,ih),min({side},iw),-2)':h='if(lte(iw,ih),-2,min({side},ih))'"
    tmp = dst.with_name(dst.stem + ".part" + dst.suffix)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "error",
        "-y",
        "-hwaccel",
        "auto",  # hardware decode where available; falls back to software
        "-i",
        str(src),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-map_metadata",
        "-1",
        "-vf",
        scale,
        "-fpsmax",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        str(tmp),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            # Software decode of 4K HEVC runs near real time on a laptop CPU.
            timeout=media_timeout(2 * info.duration_seconds, base=300.0),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        tmp.unlink(missing_ok=True)
        raise MediaError("Making a smaller working copy took too long.") from exc
    if proc.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise MediaError("Could not make a smaller working copy of the video.")
    tmp.replace(dst)
