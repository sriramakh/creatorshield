"""Longer videos: limits, frame budget, timeouts and fingerprint matching at length."""

from __future__ import annotations

import sys
import types
import uuid
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.analysis.engine import length_notes
from app.config import Settings, get_settings
from app.db import get_sessionmaker
from app.main import app
from app.media.probe import MediaError, MediaInfo, media_timeout
from app.media.working_copy import needs_working_copy
from app.models import Analysis
from app.provenance import fingerprint as fp
from app.storage import get_storage

LIMIT_VARS = [
    "MAX_DURATION_SECONDS",
    "MAX_UPLOAD_MB",
    "IMPORT_MAX_SECONDS",
    "MIN_FRAMES",
    "MAX_FRAMES",
]


def test_default_limits_cover_long_shorts_and_reels(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in LIMIT_VARS:
        monkeypatch.delenv(name, raising=False)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.max_duration_seconds == 1800
    assert s.max_upload_mb == 5120
    assert s.import_max_seconds == 1800
    assert s.catalogue_max_seconds >= s.max_duration_seconds
    assert s.job_timeout_seconds >= 5400


def test_frame_budget_grows_with_length_within_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in LIMIT_VARS:
        monkeypatch.delenv(name, raising=False)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.frame_budget(30) == 16
    assert s.frame_budget(60) == 16
    assert s.frame_budget(10 * 60) == 40
    assert s.frame_budget(20 * 60) == 64
    assert s.frame_budget(30 * 60) == 64
    assert s.frame_budget(0) == 16


def test_media_timeouts_scale_with_length() -> None:
    assert media_timeout(60) == 180
    assert media_timeout(1200) > 1200
    assert media_timeout(1200, base=300) == 1500


def test_length_notes_for_long_shorts_and_reels() -> None:
    assert length_notes("youtube_shorts", 180) == []
    assert length_notes("youtube_shorts", None) == []
    [note] = length_notes("youtube_shorts", 600)
    assert "regular video" in note and "10.0 minutes" in note
    [note] = length_notes("instagram_reels", 600)
    assert "Reels composer" in note


def _random_fp(n: int, seed: int) -> list[int]:
    rng = np.random.default_rng(seed)
    return [int(x) for x in rng.integers(0, 2**32, size=n, dtype=np.uint64)]


def test_audio_clip_shared_by_two_long_videos_is_found() -> None:
    # ~20 minutes each at Chromaprint's 0.1238 s step, sharing one ~30 s clip.
    a, other = _random_fp(9700, 1), _random_fp(9700, 2)
    b = other[:6000] + a[3000:3242] + other[6242:]
    seg = fp.match_audio(b, a)
    assert seg is not None
    assert seg.query_start == pytest.approx(6000 * fp.AUDIO_STEP, abs=1)
    assert seg.ref_start == pytest.approx(3000 * fp.AUDIO_STEP, abs=1)
    assert seg.query_end - seg.query_start == pytest.approx(242 * fp.AUDIO_STEP, abs=2)
    assert fp.match_audio(other, a) is None


def test_long_audio_self_match_and_short_clip_inside_long_audio() -> None:
    a = _random_fp(9700, 3)
    whole = fp.match_audio(a, a)
    assert whole is not None and whole.coverage == 1.0
    clip = fp.match_audio(a[2000:2240], a)
    assert clip is not None and clip.ref_start == pytest.approx(2000 * fp.AUDIO_STEP, abs=0.5)


def test_blockwise_frame_distances_equal_one_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    rng = np.random.default_rng(4)
    width = fp._BITS // 4

    def frame() -> str | None:
        if rng.random() < 0.1:
            return None
        value = int.from_bytes(rng.bytes(fp._BITS // 8), "big")
        mask = int.from_bytes(rng.bytes(fp._BITS // 8), "big")
        return f"{value & mask:0{width}x}:{mask:0{width}x}"

    q = [frame() for _ in range(37)]
    r = [frame() for _ in range(53)]
    full, _, _ = fp.frame_distance_matrix(q, r)
    monkeypatch.setattr(fp, "_PAIR_BLOCK", 100)  # forces 1-row blocks
    blocked, _, _ = fp.frame_distance_matrix(q, r)
    assert np.allclose(full, blocked)


def test_hosted_transcription_uploads_compressed_audio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    from app.media.transcribe import OpenAITranscriber

    wav = tmp_path / "audio.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=duration=20",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(wav),
        ],
        check=True,
    )
    sent: list[tuple[str, int]] = []

    class FakeTranscriptions:
        def create(self, *, file, **kwargs):  # type: ignore[no-untyped-def]
            sent.append((Path(file.name).suffix, len(file.read())))
            return types.SimpleNamespace(segments=[])

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            self.audio = types.SimpleNamespace(transcriptions=FakeTranscriptions())

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeClient))
    OpenAITranscriber("sk-test").transcribe(wav, "en")
    [(suffix, size)] = sent
    assert suffix == ".mp3"
    assert size < wav.stat().st_size / 4  # 32 kbps vs 256 kbps PCM
    assert not wav.with_suffix(".mp3").exists()


@pytest.mark.slow
def test_upload_longer_than_a_minute_is_accepted_when_the_limit_allows(
    long_video: Path, monkeypatch: pytest.MonkeyPatch, settings_override: None
) -> None:
    monkeypatch.setenv("MAX_DURATION_SECONDS", "120")
    get_settings.cache_clear()
    with TestClient(app) as client, long_video.open("rb") as fh:
        res = client.post(
            "/api/analyses",
            files={"file": (long_video.name, fh, "video/mp4")},
            data={"platform": "youtube_shorts", "language": "en"},
        )
        assert res.status_code == 202, res.text
        body = client.get(f"/api/analyses/{res.json()['id']}").json()
    assert body["status"] == "completed"
    assert body["duration_seconds"] > 60


# ---------------------------------------------------------------- working copy


def _info(width: int, height: int, bit_rate: int | None) -> MediaInfo:
    return MediaInfo(60.0, width, height, 30.0, "h264", True, "aac", "mov,mp4", bit_rate)


def test_working_copy_only_for_large_or_high_bitrate_files(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("WORKING_COPY_MAX_SHORT_SIDE", "WORKING_COPY_MAX_BITRATE_KBPS"):
        monkeypatch.delenv(name, raising=False)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert not needs_working_copy(_info(1080, 1920, 6_000_000), s)  # 1080p phone video
    assert needs_working_copy(_info(2160, 3840, 40_000_000), s)  # 4K
    assert needs_working_copy(_info(1080, 1920, 20_000_000), s)  # 1080p at 20 Mbps
    assert not needs_working_copy(_info(720, 1280, None), s)
    off = s.model_copy(
        update={"working_copy_max_short_side": 0, "working_copy_max_bitrate_kbps": 0}
    )
    assert not needs_working_copy(_info(2160, 3840, 40_000_000), off)


def _upload(client: TestClient, path: Path) -> dict:  # type: ignore[type-arg]
    with path.open("rb") as fh:
        res = client.post(
            "/api/analyses",
            files={"file": (path.name, fh, "video/mp4")},
            data={"platform": "instagram_reels", "language": "en"},
        )
    assert res.status_code == 202, res.text
    return client.get(f"/api/analyses/{res.json()['id']}").json()


@pytest.mark.slow
def test_large_upload_is_analysed_from_a_working_copy(
    sample_promo_en: Path, monkeypatch: pytest.MonkeyPatch, settings_override: None
) -> None:
    import hashlib

    monkeypatch.setenv("WORKING_COPY_MAX_SHORT_SIDE", "360")  # the 720x1280 sample counts as large
    get_settings.cache_clear()
    with TestClient(app) as client:
        body = _upload(client, sample_promo_en)
    assert body["status"] == "completed", body.get("error_message")
    info = body["media_info"]
    original_sha = hashlib.sha256(sample_promo_en.read_bytes()).hexdigest()
    assert info["working_copy"] is True
    assert info["original_sha256"] == original_sha
    assert (info["original"]["width"], info["original"]["height"]) == (720, 1280)
    assert (info["width"], info["height"]) == (360, 640)
    # Evidence and identical-file matching use the creator's original file.
    assert body["provenance"]["fingerprint"]["sha256"] == original_sha
    assert body["content_type"] == "video/mp4"
    assert body["size_bytes"] == sample_promo_en.stat().st_size
    with get_sessionmaker()() as db:
        row = db.get(Analysis, uuid.UUID(body["id"]))
        assert row is not None and row.storage_key is not None
        assert row.storage_key.endswith("/video-work.mp4")
        folder = get_storage().local_path(row.storage_key).parent
        assert sorted(p.name for p in folder.glob("video*")) == ["video-work.mp4"]


@pytest.mark.slow
def test_failed_working_copy_falls_back_to_the_original(
    sample_promo_en: Path, monkeypatch: pytest.MonkeyPatch, settings_override: None
) -> None:
    from app.analysis import engine

    def broken(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise MediaError("Could not make a smaller working copy of the video.")

    monkeypatch.setenv("WORKING_COPY_MAX_SHORT_SIDE", "360")
    monkeypatch.setattr(engine, "make_working_copy", broken)
    get_settings.cache_clear()
    with TestClient(app) as client:
        body = _upload(client, sample_promo_en)
    assert body["status"] == "completed"
    assert "working_copy" not in body["media_info"]
    assert any("analysed at its original size" in note for note in body["limitations"])


def test_file_sizes_above_two_gigabytes_are_stored(sample_promo_en: Path) -> None:
    with TestClient(app) as client:
        body = _upload(client, sample_promo_en)
    with get_sessionmaker()() as db:
        row = db.get(Analysis, uuid.UUID(body["id"]))
        assert row is not None
        row.size_bytes = 5 * 1024**3
        db.commit()
    with get_sessionmaker()() as db:
        row = db.get(Analysis, uuid.UUID(body["id"]))
        assert row is not None and row.size_bytes == 5 * 1024**3
