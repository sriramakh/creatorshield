from __future__ import annotations

from pathlib import Path

import pytest

from app.config import get_settings
from app.media.audio import subtract_intervals
from app.media.extract import run_extraction
from app.media.frames import choose_timestamps
from app.media.probe import MediaError, probe, validate_duration, validate_extension


def test_validate_extension() -> None:
    assert validate_extension("a.MOV") == (".mov", "video/quicktime")
    with pytest.raises(MediaError):
        validate_extension("a.avi")
    with pytest.raises(MediaError):
        validate_extension("noext")


def test_probe_rejects_non_video(tmp_path: Path) -> None:
    fake = tmp_path / "fake.mp4"
    fake.write_bytes(b"this is not a video" * 100)
    with pytest.raises(MediaError):
        probe(fake)


def test_probe_and_duration_limit(sample_promo_en: Path, long_video: Path) -> None:
    info = probe(sample_promo_en)
    assert info.duration_seconds == pytest.approx(27.0, abs=0.1)
    assert (info.width, info.height, info.has_audio) == (720, 1280, True)
    validate_duration(info, 60, 0.5)
    with pytest.raises(MediaError, match="limit is 60s"):
        validate_duration(probe(long_video), 60, 0.5)


def test_choose_timestamps_prefers_scene_changes_and_caps() -> None:
    picked = choose_timestamps(30, [7.0, 7.3, 21.0], interval=4, max_frames=6)
    assert len(picked) == 6
    assert picked[0] == (0.0, "first")
    assert (7.0, "scene_change") in picked and (21.0, "scene_change") in picked
    times = [t for t, _ in picked]
    assert times == sorted(times)


def test_subtract_intervals() -> None:
    assert subtract_intervals([(0, 20)], [(2, 18)], pad=0) == [(0, 2), (18, 20)]
    assert subtract_intervals([(0, 5)], [(0, 5)]) == []


@pytest.mark.slow
def test_full_extraction_on_owned_sample(sample_promo_en: Path, tmp_path: Path) -> None:
    """Real FFmpeg + faster-whisper + Tesseract on the synthetic sample."""
    info = probe(sample_promo_en)
    result = run_extraction(sample_promo_en, tmp_path, info, "en", get_settings())
    text = " ".join(s["text"] for s in result["transcript"]["segments"]).lower()
    assert "protein powder" in text and "code" in text
    assert len(result["frames"]) >= 5
    assert any("FIT50" in o["text"] for o in result["ocr"])
    non_speech = result["audio"]["non_speech_sound_intervals"]
    assert any(a >= 20 and b >= 26 for a, b in non_speech)  # the sine "music" tail
    assert (tmp_path / "frames" / "F1.jpg").exists()
