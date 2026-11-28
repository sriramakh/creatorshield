"""Compact video and audio fingerprints, and matching between two of them.

Video: a 64-bit difference hash (dHash) of every frame at ``FRAME_FPS``. FFmpeg
scales each frame to 9x8 grey pixels and the hash records whether each pixel
is brighter than its right-hand neighbour. Re-encoding, resizing and colour
grading barely change it; a mirrored copy is caught by also comparing the
horizontally flipped hash.

Audio: Chromaprint's raw fingerprint (``fpcalc -raw``), the same technique
AcoustID uses, one 32-bit value per ~0.124 s.

Neither fingerprint can be turned back into the video or the audio.

Matching needs a consistent time offset between the two videos, so two
unrelated clips filmed in the same room (similar but unaligned frames) do not
count as a copy.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.media.probe import (
    IMAGE_DEMUXERS,
    VIDEO_DEMUXERS,
    MediaError,
    input_args,
    media_timeout,
    sniff_container,
)

FRAME_FPS = 2.0
FRAME_STEP = 1.0 / FRAME_FPS
AUDIO_STEP = 0.1238  # Chromaprint default: 4096-sample hop at 11025 Hz / 3
_GRID_W, _GRID_H = 17, 16  # 16 x 16 = 256 neighbour comparisons per frame
_BITS = (_GRID_W - 1) * _GRID_H
_WORDS = _BITS // 64
_EDGE_MIN = 3  # grey levels; smaller neighbour differences are "flat", not compared
_MIN_EDGE_BITS = 24  # frames with fewer edges (black, solid colour, fades) are skipped

VIDEO_DISTANCE_MAX = 0.2  # share of edge bits that differ
VIDEO_MIN_ALIGNED = 6  # aligned frames (3 s at 2 fps)
# Alignment must be specific: a matched frame has to be clearly closer to its
# aligned reference frame than to any reference frame more than SPECIFIC_WINDOW
# frames away. Different takes on one static set look alike at *every* offset,
# so none of their frames is specific; a real copy has many.
SPECIFIC_WINDOW = 6  # frames (3 s)
SPECIFIC_MARGIN = 0.04
SPECIFIC_MIN = 3
PREFILTER_STRIDE = 4  # any run of VIDEO_MIN_ALIGNED consecutive matches contains a sample
AUDIO_BER_MAX = 0.35  # bit error rate; unrelated audio sits near 0.5
AUDIO_MIN_ITEMS = 24  # ~3 s
AUDIO_WINDOW = 16
AUDIO_CHUNK = 240  # ~30 s of query audio aligned at a time on long files
# Frame pairs compared per block. Keeps a 20-minute vs 20-minute comparison in
# tens of MB instead of over a GB.
_PAIR_BLOCK = 1 << 19

# A frame hash is "<value hex>:<edge-mask hex>". The mask marks comparisons with a
# real brightness edge; flat areas (plain backgrounds) carry no information and
# would make every text-on-colour video look alike.
FrameHash = str


@dataclass
class Fingerprint:
    duration_seconds: float
    sha256: str
    frame_step: float = FRAME_STEP
    frame_hashes: list[FrameHash | None] = field(default_factory=list)
    audio_step: float = AUDIO_STEP
    audio_fp: list[int] = field(default_factory=list)


@dataclass
class Segment:
    kind: str  # video | video_mirrored | audio
    query_start: float
    query_end: float
    ref_start: float
    ref_end: float
    coverage: float  # share of the query video covered
    score: float  # 0-1, higher = closer


# --------------------------------------------------------------------------- compute


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_grid(grid: np.ndarray) -> FrameHash | None:
    diff = grid[:, 1:] - grid[:, :-1]
    edges = (np.abs(diff) >= _EDGE_MIN).flatten()
    if int(edges.sum()) < _MIN_EDGE_BITS:
        return None
    bits = (diff > 0).flatten() & edges
    width = _BITS // 4
    value = int("".join("1" if b else "0" for b in bits), 2)
    mask = int("".join("1" if b else "0" for b in edges), 2)
    return f"{value:0{width}x}:{mask:0{width}x}"


def frame_hashes_from_raw(raw: bytes) -> list[FrameHash | None]:
    size = _GRID_W * _GRID_H
    count = len(raw) // size
    grids = np.frombuffer(raw[: count * size], dtype=np.uint8).reshape(count, _GRID_H, _GRID_W)
    return [_hash_grid(g.astype(np.int16)) for g in grids]


def video_hashes(video: Path, max_seconds: float) -> list[FrameHash | None]:
    try:
        proc = _run_video_hashes(video, max_seconds)
    except subprocess.TimeoutExpired as exc:
        raise MediaError("Reading video frames for fingerprinting took too long.") from exc
    if proc.returncode != 0:
        raise MediaError("Could not read video frames for fingerprinting.")
    return frame_hashes_from_raw(proc.stdout)


def _run_video_hashes(video: Path, max_seconds: float) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-loglevel",
            "error",
            "-t",
            f"{max_seconds:.2f}",
            *input_args(video),
            "-vf",
            f"fps={FRAME_FPS},scale={_GRID_W}:{_GRID_H}:flags=area,format=gray",
            "-f",
            "rawvideo",
            "-",
        ],
        capture_output=True,
        timeout=media_timeout(max_seconds, base=300.0),
        check=False,
    )


def audio_fingerprint(video: Path, max_seconds: float, fpcalc: str = "fpcalc") -> list[int]:
    """Chromaprint raw fingerprint, or [] when the file has no usable audio."""
    # fpcalc probes its input itself, so only hand it files sniffed as a video container.
    if sniff_container(video) not in VIDEO_DEMUXERS:
        raise MediaError("Unsupported container format for audio fingerprinting.")
    try:
        proc = subprocess.run(
            [fpcalc, "-raw", "-json", "-length", str(int(max_seconds)), str(video)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=media_timeout(max_seconds, base=300.0),
            check=False,
        )
    except FileNotFoundError as exc:
        raise MediaError(
            "Audio fingerprinting needs Chromaprint's fpcalc (brew install chromaprint)."
        ) from exc
    except subprocess.TimeoutExpired:
        return []
    if proc.returncode != 0:
        return []
    try:
        data = json.loads(proc.stdout)
        values = (data.get("fingerprint") if isinstance(data, dict) else None) or []
        return [int(v) & 0xFFFFFFFF for v in values]
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def compute_fingerprint(
    video: Path,
    duration: float,
    max_seconds: float,
    fpcalc: str = "fpcalc",
    sha256: str | None = None,
) -> Fingerprint:
    """``sha256`` is the original file's hash when ``video`` is a working copy."""
    limit = min(duration, max_seconds)
    return Fingerprint(
        duration_seconds=round(duration, 2),
        sha256=sha256 or file_sha256(video),
        frame_hashes=video_hashes(video, limit),
        audio_fp=audio_fingerprint(video, limit, fpcalc),
    )


# --------------------------------------------------------------------------- match


def _split(h: FrameHash) -> tuple[int, int]:
    value, mask = h.split(":")
    return int(value, 16), int(mask, 16)


def _mirror_bits(bits: int, invert: bool) -> int:
    """Reverse each 16-comparison row; a flipped frame also inverts brighter/darker."""
    row_bits = _GRID_W - 1
    row_mask = (1 << row_bits) - 1
    out = 0
    for row in range(_GRID_H):
        chunk = (bits >> ((_GRID_H - 1 - row) * row_bits)) & row_mask
        flipped = int(f"{chunk:0{row_bits}b}"[::-1], 2)
        out = (out << row_bits) | flipped
    return out


def mirror_hash(h: FrameHash) -> FrameHash:
    value, mask = _split(h)
    mirrored_mask = _mirror_bits(mask, invert=False)
    # Edge bits flip direction; non-edge bits stay 0.
    mirrored_value = _mirror_bits(value ^ mask, invert=False) & mirrored_mask
    width = _BITS // 4
    return f"{mirrored_value:0{width}x}:{mirrored_mask:0{width}x}"


def _words(n: int) -> list[int]:
    return [(n >> (64 * (_WORDS - 1 - i))) & 0xFFFFFFFFFFFFFFFF for i in range(_WORDS)]


@dataclass
class HashArrays:
    """Frame hashes parsed once into bit arrays (parsing hex is the slow part)."""

    values: np.ndarray
    masks: np.ndarray
    ok: np.ndarray

    def __len__(self) -> int:
        return int(self.ok.size)

    def take(self, index: np.ndarray) -> HashArrays:
        return HashArrays(self.values[index], self.masks[index], self.ok[index])


def hash_arrays(hashes: list[FrameHash | None]) -> HashArrays:
    values = np.zeros((len(hashes), _WORDS), dtype=np.uint64)
    masks = np.zeros((len(hashes), _WORDS), dtype=np.uint64)
    ok = np.zeros(len(hashes), dtype=bool)
    for i, h in enumerate(hashes):
        if h is None:
            continue
        v, m = _split(h)
        values[i] = _words(v)
        masks[i] = _words(m)
        ok[i] = True
    return HashArrays(values, masks, ok)


def _pop(a: np.ndarray) -> np.ndarray:
    return np.bitwise_count(a).sum(axis=-1).astype(np.float32)


def _distances(q: HashArrays, r: HashArrays) -> np.ndarray:
    dist = np.ones((len(q), len(r)), dtype=np.float32)
    rv, rm = r.values, r.masks
    rows = max(1, _PAIR_BLOCK // max(1, len(r)))
    for a in range(0, len(q), rows):
        bv, bm = q.values[a : a + rows, None, :], q.masks[a : a + rows, None, :]
        both = bm & rm[None, :, :]
        flipped = _pop((bv ^ rv[None, :, :]) & both)
        only_one = _pop(bm ^ rm[None, :, :])
        dist[a : a + rows] = (flipped + 0.5 * only_one) / np.maximum(_pop(bm | rm[None, :, :]), 1)
    dist[~q.ok, :] = 1.0
    dist[:, ~r.ok] = 1.0
    return dist


def frame_distance_matrix(
    query: list[FrameHash | None], ref: list[FrameHash | None]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pairwise distance in [0, 1] (1 = unrelated) plus validity masks.

    Distance counts edges pointing the other way, plus half of the edges present
    in only one frame, over all edges present in either frame.
    """
    q, r = hash_arrays(query), hash_arrays(ref)
    return _distances(q, r), q.ok, r.ok


@dataclass
class PreparedQuery:
    """A query fingerprint parsed once for comparison with many catalogue entries."""

    fp: Fingerprint
    direct: HashArrays
    mirrored: HashArrays
    sample: np.ndarray  # query frames used by the cheap pre-filter


def prepare(fp: Fingerprint) -> PreparedQuery:
    hashes = fp.frame_hashes
    direct = hash_arrays(hashes)
    mirrored = hash_arrays([mirror_hash(h) if h is not None else None for h in hashes])
    valid = np.nonzero(direct.ok)[0]
    return PreparedQuery(fp, direct, mirrored, valid[::PREFILTER_STRIDE])


def video_may_match(pq: PreparedQuery, ref: HashArrays) -> bool:
    """Cheap test on every PREFILTER_STRIDE-th valid query frame. False means no video
    match is possible: a 3 s run of matching frames always contains a sampled frame."""
    if int(pq.direct.ok.sum()) < VIDEO_MIN_ALIGNED or int(ref.ok.sum()) < VIDEO_MIN_ALIGNED:
        return False
    if pq.sample.size == 0:
        return False
    for arrays in (pq.direct, pq.mirrored):
        if float(_distances(arrays.take(pq.sample), ref).min()) <= VIDEO_DISTANCE_MAX:
            return True
    return False


def _specific_frames(dist: np.ndarray, rows: np.ndarray, offset: int) -> int:
    """How many matched query frames are clearly closer to their aligned reference
    frame than to any reference frame outside the alignment window."""
    m = dist.shape[1]
    if rows.size == 0 or m == 0:
        return 0
    cols = np.arange(m, dtype=np.int32)
    block = max(1, _PAIR_BLOCK // m)
    count = 0
    for a in range(0, rows.size, block):
        part = rows[a : a + block].astype(np.int32)
        sub = dist[part]
        gap = np.abs(cols[None, :] - (part[:, None] + offset))
        near = np.where(gap <= 1, sub, np.inf).min(axis=1)
        far = np.where(gap > SPECIFIC_WINDOW, sub, np.inf).min(axis=1)
        far = np.minimum(far, 1.0)  # nothing outside the window: nothing to confuse it with
        count += int(np.count_nonzero(far - near >= SPECIFIC_MARGIN))
    return count


def _segment(q: HashArrays, r: HashArrays, step: float, mirrored: bool) -> Segment | None:
    if q.ok.sum() < VIDEO_MIN_ALIGNED or r.ok.sum() < VIDEO_MIN_ALIGNED:
        return None
    dist = _distances(q, r)
    qi, ri = np.nonzero(dist <= VIDEO_DISTANCE_MAX)
    if qi.size == 0:
        return None
    # Vote for the time offset, weighting closer frames more.
    shift = len(q) - 1  # offsets start at -(len(query) - 1)
    votes = np.bincount(ri - qi + shift, weights=1.0 - dist[qi, ri] / VIDEO_DISTANCE_MAX)
    best_offset = int(np.argmax(votes)) - shift
    aligned = np.abs((ri - qi) - best_offset) <= 1
    matched_q = np.unique(qi[aligned])
    if matched_q.size < VIDEO_MIN_ALIGNED:
        return None
    if _specific_frames(dist, matched_q, best_offset) < SPECIFIC_MIN:
        return None  # alike at every offset: a shared set or template, not a copy
    valid_query = int(q.ok.sum())
    start, end = int(matched_q.min()), int(matched_q.max())
    return Segment(
        kind="video_mirrored" if mirrored else "video",
        query_start=round(start * step, 2),
        query_end=round((end + 1) * step, 2),
        ref_start=round(max(0, start + best_offset) * step, 2),
        ref_end=round((end + 1 + best_offset) * step, 2),
        coverage=round(min(1.0, matched_q.size / valid_query), 3),
        score=round(1 - float(dist[qi[aligned], ri[aligned]].mean()), 3),
    )


def _video_segment(
    query: list[FrameHash | None], ref: list[FrameHash | None], step: float, mirrored: bool
) -> Segment | None:
    if mirrored:
        query = [mirror_hash(h) if h is not None else None for h in query]
    return _segment(hash_arrays(query), hash_arrays(ref), step, mirrored)


def _best_video(pq: PreparedQuery, ref: HashArrays, step: float) -> Segment | None:
    direct = _segment(pq.direct, ref, step, mirrored=False)
    flipped = _segment(pq.mirrored, ref, step, mirrored=True)
    if flipped is not None and (
        direct is None or (flipped.coverage, flipped.score) > (direct.coverage, direct.score)
    ):
        return flipped
    return direct


def match_video(
    query: list[FrameHash | None], ref: list[FrameHash | None], step: float
) -> Segment | None:
    pq = prepare(Fingerprint(duration_seconds=0.0, sha256="", frame_hashes=query))
    return _best_video(pq, hash_arrays(ref), step)


def _informative(values: np.ndarray) -> np.ndarray:
    """False where the fingerprint is static (silence or a held tone)."""
    mask = np.ones(values.size, dtype=bool)
    mask[1:] = values[1:] != values[:-1]
    return mask


def _audio_offsets(
    q: np.ndarray, q_mask: np.ndarray, r: np.ndarray, r_mask: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Bit error rate of ``q`` at every offset across ``r`` (index k is offset k - len(q) + 1)."""
    n = q.size
    pad = np.zeros(n - 1, dtype=np.uint32)
    no = np.zeros(n - 1, dtype=bool)
    windows = np.lib.stride_tricks.sliding_window_view(np.concatenate([pad, r, pad]), n)
    window_ok = np.lib.stride_tricks.sliding_window_view(np.concatenate([no, r_mask, no]), n)
    window_ok = window_ok & q_mask[None, :]
    errors = np.where(window_ok, np.bitwise_count(windows ^ q[None, :]), 0).sum(axis=1)
    overlap = window_ok.sum(axis=1)
    ber = np.where(overlap >= AUDIO_MIN_ITEMS, errors / np.maximum(overlap, 1) / 32, 1.0)
    return ber, overlap


def _best_audio_offset(
    q: np.ndarray, q_mask: np.ndarray, r: np.ndarray, r_mask: np.ndarray
) -> int | None:
    """Offset (ref index - query index) where the query lines up with the reference.

    Short queries are slid across the reference whole. Long ones are split into
    ~30 s chunks that each find their own best offset and vote: memory stays small,
    and a clip reused inside a longer video still lines up even though the rest of
    the video does not.
    """
    n = q.size
    limit = AUDIO_BER_MAX + 0.05
    if n <= 2 * AUDIO_CHUNK:
        ber, _ = _audio_offsets(q, q_mask, r, r_mask)
        best = int(np.argmin(ber))
        return best - (n - 1) if ber[best] <= limit else None
    votes: dict[int, float] = {}
    for start in range(0, n, AUDIO_CHUNK):
        chunk, mask = q[start : start + AUDIO_CHUNK], q_mask[start : start + AUDIO_CHUNK]
        if mask.sum() < AUDIO_MIN_ITEMS:
            continue
        ber, overlap = _audio_offsets(chunk, mask, r, r_mask)
        best = int(np.argmin(ber))
        if ber[best] <= limit:
            offset = best - (chunk.size - 1) - start
            votes[offset] = votes.get(offset, 0.0) + float(overlap[best]) * (1 - float(ber[best]))
    if not votes:
        return None
    # Re-encodes can shift the hop grid by one item; pool neighbouring offsets.
    return max(votes, key=lambda o: votes[o] + 0.5 * (votes.get(o - 1, 0) + votes.get(o + 1, 0)))


def match_audio(query: list[int], ref: list[int], step: float = AUDIO_STEP) -> Segment | None:
    if len(query) < AUDIO_MIN_ITEMS or len(ref) < AUDIO_MIN_ITEMS:
        return None
    q = np.array(query, dtype=np.uint32)
    r = np.array(ref, dtype=np.uint32)
    q_mask = _informative(q)
    if q_mask.sum() < AUDIO_MIN_ITEMS:
        return None
    r_mask = _informative(r)
    offset = _best_audio_offset(q, q_mask, r, r_mask)
    if offset is None:
        return None
    n, m = q.size, r.size
    # Per-item errors along the chosen alignment (ref index = query index + offset).
    ref_idx = np.arange(n) + offset
    inside = (ref_idx >= 0) & (ref_idx < m)
    aligned = r[np.clip(ref_idx, 0, m - 1)]
    ok = inside & q_mask & r_mask[np.clip(ref_idx, 0, m - 1)]
    per_item = np.bitwise_count(q ^ aligned).astype(np.float32) / 32
    kernel = np.ones(AUDIO_WINDOW, dtype=np.float32)
    local_err = np.convolve(np.where(ok, per_item, 0), kernel, "same")
    local_n = np.convolve(ok.astype(np.float32), kernel, "same")
    matched = (local_n >= AUDIO_WINDOW / 4) & (local_err / np.maximum(local_n, 1) <= AUDIO_BER_MAX)
    # Longest contiguous matched run.
    run_start, run_end, cur_start = 0, 0, None
    for i, flag in enumerate([*matched.tolist(), False]):
        if flag and cur_start is None:
            cur_start = i
        elif not flag and cur_start is not None:
            if i - cur_start > run_end - run_start:
                run_start, run_end = cur_start, i
            cur_start = None
    end = run_end
    if end - run_start < AUDIO_MIN_ITEMS:
        return None
    run_ber = float(per_item[run_start:end][ok[run_start:end]].mean())
    return Segment(
        kind="audio",
        query_start=round(run_start * step, 2),
        query_end=round(end * step, 2),
        ref_start=round(max(0, run_start + offset) * step, 2),
        ref_end=round(min(m, end + offset) * step, 2),
        coverage=round((end - run_start) / n, 3),
        score=round(1 - run_ber, 3),
    )


def compare(query: Fingerprint, ref: Fingerprint) -> dict[str, Any] | None:
    """Summarise how ``query`` overlaps ``ref``; None when nothing meaningful matches."""
    return compare_prepared(prepare(query), ref, prefilter=False)


def compare_prepared(
    pq: PreparedQuery,
    ref: Fingerprint,
    *,
    ref_arrays: HashArrays | None = None,
    prefilter: bool = True,
) -> dict[str, Any] | None:
    """Like :func:`compare` for a query prepared once and compared with many entries."""
    query = pq.fp
    arrays = ref_arrays if ref_arrays is not None else hash_arrays(ref.frame_hashes)
    video = None
    if not prefilter or video_may_match(pq, arrays):
        video = _best_video(pq, arrays, query.frame_step)
    audio = match_audio(query.audio_fp, ref.audio_fp, query.audio_step)
    return _summary(video, audio)


def _summary(video: Segment | None, audio: Segment | None) -> dict[str, Any] | None:
    if video is None and audio is None:
        return None
    if video is not None and audio is not None and _same_offset(video, audio):
        kind = "same_clip"
    elif video is not None:
        kind = "mirrored_footage" if video.kind == "video_mirrored" else "same_footage"
    else:
        kind = "same_audio"
    primary = video or audio
    assert primary is not None
    return {
        "kind": kind,
        "query_start": primary.query_start,
        "query_end": primary.query_end,
        "ref_start": primary.ref_start,
        "ref_end": primary.ref_end,
        "video_coverage": video.coverage if video else 0.0,
        "audio_coverage": audio.coverage if audio else 0.0,
        "video_score": video.score if video else None,
        "audio_score": audio.score if audio else None,
        "audio_segment": (
            {
                "query_start": audio.query_start,
                "query_end": audio.query_end,
                "ref_start": audio.ref_start,
                "ref_end": audio.ref_end,
            }
            if audio
            else None
        ),
    }


def _same_offset(video: Segment, audio: Segment, tolerance: float = 1.5) -> bool:
    """True when video and audio point at the same place in the reference.

    Overlap on the query timeline is not enough: a visual hit and a music bed
    can share screen time while sitting minutes apart in the other video.
    """
    video_offset = video.ref_start - video.query_start
    audio_offset = audio.ref_start - audio.query_start
    return abs(video_offset - audio_offset) <= tolerance


def thumbnail_hash(image: Path) -> FrameHash | None:
    """Hash of a still image (e.g. a YouTube thumbnail), on the same grid as frames.

    None for blank images and for anything that is not a JPEG, PNG or WebP file."""
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostdin",
                "-loglevel",
                "error",
                *input_args(image, IMAGE_DEMUXERS),
                "-vf",
                f"scale={_GRID_W}:{_GRID_H}:flags=area,format=gray",
                "-frames:v",
                "1",
                "-f",
                "rawvideo",
                "-",
            ],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (MediaError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or len(proc.stdout) < _GRID_W * _GRID_H:
        return None
    return frame_hashes_from_raw(proc.stdout)[0]


def nearest_frame(
    target: FrameHash, hashes: list[FrameHash | None], step: float
) -> tuple[float, float] | None:
    """(distance 0-1, timestamp) of the closest frame, mirrored frames included."""
    if not any(h is not None for h in hashes):
        return None
    direct, _, _ = frame_distance_matrix([target], hashes)
    mirrored, _, _ = frame_distance_matrix([mirror_hash(target)], hashes)
    dist = np.minimum(direct[0], mirrored[0])
    i = int(np.argmin(dist))
    return round(float(dist[i]), 3), round(i * step, 2)
