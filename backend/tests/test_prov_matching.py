"""Fingerprint matching specificity, bounded catalogue comparison and safe media inputs."""

from __future__ import annotations

import itertools
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from app.media.probe import MediaError, input_args, probe, sniff_container
from app.models import MediaFingerprint
from app.provenance import fingerprint as F

# --------------------------------------------------------------------------- 4: static sets

_SET = np.random.default_rng(1).integers(40, 200, size=(16, 17)).astype(np.int16)


def _take(n: int, seed: int) -> list[np.ndarray]:
    """One take on a static set: sensor noise plus a person moving in the frame."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        g = _SET + rng.normal(0, 4, size=_SET.shape).astype(np.int16)
        x = int(6 + 3 * np.sin(i / 5 + seed))
        g[6:14, x : x + 4] = rng.integers(0, 255, size=(8, 4))
        out.append(np.clip(g, 0, 255).astype(np.int16))
    return out


def _moving(n: int, seed: int) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    wide = rng.integers(0, 255, size=(16, 60)).astype(np.int16)
    return [wide[:, (i // 3) % 43 : (i // 3) % 43 + 17] for i in range(n)]


def _reencode(grids: list[np.ndarray], seed: int) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    return [
        np.clip(g + 6 + rng.normal(0, 1.5, size=g.shape), 0, 255).astype(np.int16) for g in grids
    ]


def _fp(grids: list[np.ndarray]) -> F.Fingerprint:
    hashes = [F._hash_grid(g) for g in grids]
    return F.Fingerprint(
        duration_seconds=len(grids) * F.FRAME_STEP, sha256="x", frame_hashes=hashes
    )


def test_different_takes_on_one_static_set_do_not_match() -> None:
    assert F.compare(_fp(_take(120, 2)), _fp(_take(120, 3))) is None
    assert F.compare(_fp(_take(120, 5)), _fp(_take(120, 7))) is None


def test_copies_still_match_after_the_specificity_check() -> None:
    take = _take(120, 2)
    reenc = F.compare(_fp(_reencode(take, 9)), _fp(take))
    assert reenc is not None and reenc["kind"] == "same_footage"

    clip = _moving(120, 4)
    assert F.compare(_fp(_reencode(clip, 1)), _fp(clip))["video_coverage"] > 0.9  # type: ignore[index]
    trimmed = F.compare(_fp(_reencode(clip[30:80], 1)), _fp(clip))
    assert trimmed is not None and trimmed["ref_start"] == pytest.approx(15.0, abs=0.5)
    mirrored = F.compare(_fp([g[:, ::-1].copy() for g in _reencode(clip, 2)]), _fp(clip))
    assert mirrored is not None and mirrored["kind"] == "mirrored_footage"


def test_prefilter_never_hides_a_real_match() -> None:
    clip = _moving(120, 4)
    pq = F.prepare(_fp(_reencode(clip[30:80], 1)))
    ref = F.hash_arrays(_fp(clip).frame_hashes)
    assert F.video_may_match(pq, ref)
    other = F.hash_arrays(_fp(_moving(120, 11)).frame_hashes)
    assert not F.video_may_match(pq, other)


# --------------------------------------------------------------------------- 10: catalogue bound


def _row(**kw: Any) -> MediaFingerprint:

    base = {
        "source": "catalogue",
        "owner_label": "Client B",
        "duration_seconds": 60.0,
        "sha256": "0" * 64,
        "frame_step": 0.5,
        "frame_hashes": _fp(_moving(120, 4)).frame_hashes,
        "audio_fp": [],
        "expires_at": datetime.now(UTC) + timedelta(days=30),
    }
    return MediaFingerprint(**(base | kw))


def test_catalogue_comparison_stops_at_its_time_budget_but_still_checks_identical_files() -> None:
    from app.config import get_settings
    from app.db import get_sessionmaker
    from app.provenance.catalogue import find_matches
    from app.provenance.findings import build

    clip = _moving(120, 4)
    query = _fp(_reencode(clip, 1))
    query.sha256 = "ab" * 32
    with get_sessionmaker()() as db:
        for i in range(5):
            db.add(_row(sha256=f"{i:064d}"))
        db.add(_row(sha256="ab" * 32, frame_hashes=[]))  # byte-identical entry
        db.commit()
        ticks = itertools.count(0, 1000)  # every clock() call jumps past the budget
        out = find_matches(db, query, "Client A", None, get_settings(), clock=lambda: next(ticks))
    assert out["truncated"] and "time limit" in out["truncated_note"]
    assert out["entries_compared"] < 5
    assert [m["kind"] for m in out["matches"]] == ["identical_file"]

    _, lines = build(
        provenance={"catalogue": out},
        platform="youtube_shorts",
        client_label="Client A",
        caption="",
        hashtags=[],
        extraction={},
        entries=[],
        connected=set(),
        today=datetime.now(UTC).date(),
    )
    assert any(line["status"] == "review" and "incomplete" in line["subject"] for line in lines)


def test_catalogue_comparison_within_budget_finds_the_copy() -> None:
    from app.config import get_settings
    from app.db import get_sessionmaker
    from app.provenance.catalogue import find_matches

    clip = _moving(120, 4)
    with get_sessionmaker()() as db:
        db.add(_row())
        db.add(_row(sha256="1" * 64, frame_hashes=[None] * 10))  # too blank: skipped cheaply
        db.commit()
        out = find_matches(db, _fp(_reencode(clip, 1)), "Client A", None, get_settings())
    assert not out.get("truncated")
    assert [m["kind"] for m in out["matches"]] == ["same_footage"]


# --------------------------------------------------------------------------- 11: safe inputs


def test_playlists_and_unknown_files_are_never_handed_to_ffmpeg(tmp_path: Path) -> None:
    playlist = tmp_path / "video.mp4"
    playlist.write_text(
        "#EXTM3U\n#EXT-X-TARGETDURATION:10\n#EXTINF:10,\nhttp://169.254.169.254/latest\n",
        encoding="utf-8",
    )
    assert sniff_container(playlist) is None
    with pytest.raises(MediaError, match="Unsupported"):
        probe(playlist)
    with pytest.raises(MediaError):
        input_args(playlist)
    concat = tmp_path / "x.mov"
    concat.write_text("ffconcat version 1.0\nfile /etc/passwd\n", encoding="utf-8")
    with pytest.raises(MediaError):
        probe(concat)


def test_input_args_force_the_sniffed_demuxer_and_file_protocol(tmp_path: Path) -> None:
    mp4 = tmp_path / "a.bin"
    mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16)
    assert input_args(mp4) == ["-protocol_whitelist", "file", "-f", "mov", "-i", str(mp4)]
    mkv = tmp_path / "b.webm"
    mkv.write_bytes(bytes.fromhex("1a45dfa3") + b"\x00" * 16)
    assert input_args(mkv)[3] == "matroska"
    jpg = tmp_path / "c.jpg"
    jpg.write_bytes(bytes.fromhex("ffd8ffe0") + b"\x00" * 16)
    with pytest.raises(MediaError):
        input_args(jpg)  # an image is not accepted where a video is expected


def test_thumbnail_paths_refuse_non_images_and_remove_the_download(tmp_path: Path) -> None:
    from app.integrations.importer import thumbnail_to_frame

    fake = tmp_path / "cover.src"
    fake.write_text("#EXTM3U\nfile:///etc/passwd\n", encoding="utf-8")
    with pytest.raises(MediaError):
        thumbnail_to_frame(fake, tmp_path / "cover.jpg")
    assert not fake.exists()
    assert F.thumbnail_hash(tmp_path / "missing.jpg") is None


@pytest.mark.slow
def test_real_ffmpeg_reads_files_through_the_safe_inputs(tmp_path: Path) -> None:
    clip = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=160x284:d=3",
         "-c:v", "libx264", "-preset", "ultrafast", str(clip)],
        check=True,
    )  # fmt: skip
    assert probe(clip).duration_seconds == pytest.approx(3, abs=0.2)
    assert sum(1 for h in F.video_hashes(clip, 3) if h) >= 4
    thumb = tmp_path / "t.jpg"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(clip), "-frames:v", "1", str(thumb)],
        check=True,
    )
    assert F.thumbnail_hash(thumb) is not None
