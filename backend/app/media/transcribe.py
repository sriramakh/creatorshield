"""Pluggable speech-to-text.

``faster_whisper`` runs locally (CTranslate2, int8 on CPU; time grows with the
length of speech). ``openai`` uses the hosted transcription API (paid). The
local model is loaded once per worker process and reused.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from app.config import Settings
from app.media.audio import wav_duration
from app.media.probe import MediaError, media_timeout

log = logging.getLogger(__name__)


@dataclass
class Segment:
    id: str
    start: float
    end: float
    text: str


@dataclass
class Transcript:
    provider: str
    model: str | None
    language: str | None
    language_probability: float | None
    segments: list[Segment]

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "language": self.language,
            "language_probability": self.language_probability,
            "segments": [asdict(s) for s in self.segments],
        }


def load_wav_16k_mono(path: Path) -> Any:
    """Read the 16 kHz mono PCM WAV written by ``extract_audio`` as float32 samples."""
    import numpy as np

    with wave.open(str(path), "rb") as wf:
        if wf.getnchannels() != 1 or wf.getframerate() != 16000 or wf.getsampwidth() != 2:
            raise ValueError("expected 16 kHz mono 16-bit PCM WAV")
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


class Transcriber(Protocol):
    def transcribe(self, audio: Path, language: str) -> Transcript: ...


class FasterWhisperTranscriber:
    _model_cache: dict[tuple[str, str], Any] = {}
    _lock = threading.Lock()

    def __init__(self, model_size: str, compute_type: str) -> None:
        self.model_size = model_size
        self.compute_type = compute_type

    def _model(self) -> Any:
        key = (self.model_size, self.compute_type)
        with self._lock:
            if key not in self._model_cache:
                from faster_whisper import WhisperModel

                log.info("loading faster-whisper model %s (%s)", *key)
                self._model_cache[key] = WhisperModel(
                    self.model_size, device="cpu", compute_type=self.compute_type
                )
            return self._model_cache[key]

    def transcribe(self, audio: Path, language: str) -> Transcript:
        # Pass decoded samples rather than a path: faster-whisper's own decoder
        # depends on PyAV APIs that change between releases.
        segments_iter, info = self._model().transcribe(
            load_wav_16k_mono(audio),
            language=language,
            vad_filter=True,  # suppresses hallucinated text over music/silence
            beam_size=5,
            condition_on_previous_text=False,
        )
        segments = [
            Segment(
                id=f"T{i + 1}", start=round(s.start, 2), end=round(s.end, 2), text=s.text.strip()
            )
            for i, s in enumerate(segments_iter)
            if s.text.strip()
        ]
        return Transcript(
            provider="faster_whisper",
            model=self.model_size,
            language=info.language,
            language_probability=round(info.language_probability, 3),
            segments=segments,
        )


class OpenAITranscriber:
    def __init__(self, api_key: str, model: str = "whisper-1") -> None:
        self.api_key = api_key
        self.model = model

    def transcribe(self, audio: Path, language: str) -> Transcript:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        # The hosted API takes files up to 25 MB; 16 kHz PCM passes that at about
        # 13 minutes. 32 kbps mono MP3 keeps 20 minutes under 5 MB.
        upload = audio.with_suffix(".mp3")
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostdin",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(audio),
                "-ac",
                "1",
                "-b:a",
                "32k",
                str(upload),
            ],
            capture_output=True,
            text=True,
            timeout=media_timeout(wav_duration(audio)),
            check=False,
        )
        if proc.returncode != 0:
            raise MediaError("Could not prepare the audio for transcription.")
        try:
            with upload.open("rb") as fh:
                result = client.audio.transcriptions.create(
                    model=self.model,
                    file=fh,
                    language=language,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                )
        finally:
            upload.unlink(missing_ok=True)
        segments = [
            Segment(
                id=f"T{i + 1}", start=round(s.start, 2), end=round(s.end, 2), text=s.text.strip()
            )
            for i, s in enumerate(result.segments or [])
            if s.text.strip()
        ]
        return Transcript("openai", self.model, language, None, segments)


class NoTranscriber:
    def transcribe(self, audio: Path, language: str) -> Transcript:
        return Transcript("none", None, None, None, [])


def get_transcriber(settings: Settings) -> Transcriber:
    if settings.stt_provider == "faster_whisper":
        return FasterWhisperTranscriber(settings.whisper_model, settings.whisper_compute_type)
    if settings.stt_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("STT_PROVIDER=openai requires OPENAI_API_KEY")
        return OpenAITranscriber(settings.openai_api_key.get_secret_value())
    return NoTranscriber()
