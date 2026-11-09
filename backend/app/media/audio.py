"""Audio extraction and non-speech sound detection."""

from __future__ import annotations

import re
import subprocess
import wave
from pathlib import Path

from app.media.probe import MediaError, media_timeout

_SIL_START = re.compile(r"silence_start: (-?[0-9.]+)")
_SIL_END = re.compile(r"silence_end: ([0-9.]+)")


def extract_audio(video: Path, out: Path, timeout: float = 120.0) -> None:
    """16 kHz mono WAV, the input format speech-to-text models expect."""
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0 or not out.exists():
        raise MediaError("Could not extract the audio track.")


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def sound_intervals(
    audio: Path, duration: float, noise_db: float = -40.0, min_silence: float = 0.4
) -> list[tuple[float, float]]:
    """Intervals that are *not* silent, via FFmpeg silencedetect.

    ``duration`` is the video duration; the audio track may be shorter, in
    which case its real length is used so the missing tail is not "sound".
    """
    duration = min(duration, wav_duration(audio))
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-i",
            str(audio),
            "-af",
            f"silencedetect=noise={noise_db}dB:d={min_silence}",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        timeout=media_timeout(duration),
        check=False,
    )
    if proc.returncode != 0:
        raise MediaError("Audio analysis failed.")
    starts = [max(0.0, float(m.group(1))) for m in _SIL_START.finditer(proc.stderr)]
    ends = [float(m.group(1)) for m in _SIL_END.finditer(proc.stderr)]
    silences = list(zip(starts, ends + [duration] * (len(starts) - len(ends)), strict=False))
    sound: list[tuple[float, float]] = []
    cursor = 0.0
    for s, e in silences:
        if s > cursor:
            sound.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < duration:
        sound.append((cursor, duration))
    return [(round(a, 2), round(b, 2)) for a, b in sound if b - a >= 0.3]


def subtract_intervals(
    base: list[tuple[float, float]], remove: list[tuple[float, float]], pad: float = 0.3
) -> list[tuple[float, float]]:
    """``base`` minus ``remove`` (each remove interval padded by ``pad``)."""
    result: list[tuple[float, float]] = []
    for b_start, b_end in base:
        pieces = [(b_start, b_end)]
        for r_start, r_end in remove:
            r_start, r_end = r_start - pad, r_end + pad
            next_pieces = []
            for p_start, p_end in pieces:
                if r_end <= p_start or r_start >= p_end:
                    next_pieces.append((p_start, p_end))
                    continue
                if r_start > p_start:
                    next_pieces.append((p_start, r_start))
                if r_end < p_end:
                    next_pieces.append((r_end, p_end))
            pieces = next_pieces
        result.extend(pieces)
    return [(round(a, 2), round(b, 2)) for a, b in result if b - a >= 1.0]
