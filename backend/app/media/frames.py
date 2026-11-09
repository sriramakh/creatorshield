"""Representative frame sampling: scene changes + uniform coverage."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.media.probe import MediaError

_PTS_RE = re.compile(r"pts_time:([0-9.]+)")


@dataclass
class Frame:
    id: str
    timestamp: float
    reason: str  # "scene_change" | "uniform" | "first"
    path: Path


def detect_scene_changes(video: Path, threshold: float, timeout: float = 120.0) -> list[float]:
    """Timestamps (seconds) where FFmpeg's scene score exceeds ``threshold``."""
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-i",
            str(video),
            "-vf",
            f"select='gt(scene,{threshold})',showinfo",
            "-an",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise MediaError("Scene detection failed.")
    return [float(m.group(1)) for m in _PTS_RE.finditer(proc.stderr)]


def choose_timestamps(
    duration: float,
    scene_times: list[float],
    interval: float,
    max_frames: int,
    min_gap: float = 1.0,
) -> list[tuple[float, str]]:
    """Merge scene-change and uniform timestamps, de-duplicate, cap at ``max_frames``.

    Scene changes win over uniform samples when they are within ``min_gap``.
    """
    candidates: list[tuple[float, str]] = [(0.0, "first")]
    candidates += [(t, "scene_change") for t in scene_times if 0 < t < duration]
    t = interval
    while t < duration - 0.25:
        candidates.append((round(t, 3), "uniform"))
        t += interval
    priority = {"first": 0, "scene_change": 1, "uniform": 2}
    chosen: list[tuple[float, str]] = []
    for ts, reason in sorted(candidates, key=lambda c: (priority[c[1]], c[0])):
        if all(abs(ts - c[0]) >= min_gap for c in chosen):
            chosen.append((ts, reason))
    if len(chosen) > max_frames:
        # Keep the first frame and scene changes (most informative), then fill
        # the remaining slots with evenly spread uniform samples.
        first = chosen[0]
        scenes = sorted((c for c in chosen if c[1] == "scene_change"), key=lambda c: c[0])
        uniform = sorted((c for c in chosen if c[1] == "uniform"), key=lambda c: c[0])
        if len(scenes) >= max_frames - 1:
            step = len(scenes) / (max_frames - 1)
            scenes = [scenes[int(i * step)] for i in range(max_frames - 1)]
            uniform = []
        else:
            slots = max_frames - 1 - len(scenes)
            step = len(uniform) / slots
            uniform = [uniform[int(i * step)] for i in range(slots)]
        chosen = [first, *scenes, *uniform]
    return sorted(chosen, key=lambda c: c[0])


def extract_frame(video: Path, timestamp: float, out: Path, width: int) -> None:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-vf",
            f"scale='min({width},iw)':-2",
            "-q:v",
            "4",
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0 or not out.exists():
        raise MediaError(f"Could not extract frame at {timestamp:.2f}s.")


def sample_frames(
    video: Path,
    out_dir: Path,
    duration: float,
    *,
    threshold: float,
    interval: float,
    max_frames: int,
    width: int,
) -> list[Frame]:
    out_dir.mkdir(parents=True, exist_ok=True)
    scenes = detect_scene_changes(video, threshold)
    frames: list[Frame] = []
    for i, (ts, reason) in enumerate(choose_timestamps(duration, scenes, interval, max_frames)):
        # Seeking exactly to a scene cut can land on the last frame of the
        # previous shot; nudge forward slightly.
        seek = min(ts + 0.05, max(duration - 0.05, 0)) if reason == "scene_change" else ts
        path = out_dir / f"F{i + 1}.jpg"
        extract_frame(video, seek, path, width)
        frames.append(Frame(id=f"F{i + 1}", timestamp=round(ts, 2), reason=reason, path=path))
    return frames
