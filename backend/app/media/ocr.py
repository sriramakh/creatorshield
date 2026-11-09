"""On-screen text detection with the Tesseract CLI."""

from __future__ import annotations

import csv
import io
import subprocess
from dataclasses import dataclass
from pathlib import Path

TESS_LANGS = {"en": "eng", "hi": "hin+eng"}


@dataclass
class OcrResult:
    id: str
    frame_id: str
    timestamp: float
    text: str
    mean_confidence: float


def ocr_image(image: Path, language: str, tesseract_cmd: str = "tesseract") -> tuple[str, float]:
    """Return (text, mean word confidence 0-100). Low-confidence words are dropped."""
    proc = subprocess.run(
        [
            tesseract_cmd,
            str(image),
            "stdout",
            "-l",
            TESS_LANGS.get(language, "eng"),
            "--psm",
            "11",
            "tsv",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        return "", 0.0
    words: list[str] = []
    confs: list[float] = []
    reader = csv.DictReader(io.StringIO(proc.stdout), delimiter="\t", quoting=csv.QUOTE_NONE)
    for row in reader:
        text = (row.get("text") or "").strip()
        try:
            conf = float(row.get("conf") or -1)
        except ValueError:
            conf = -1
        # psm 11 (sparse text) on video frames produces many junk tokens;
        # keep only reasonably confident, non-trivial words.
        if text and conf >= 70 and (len(text) > 1 or text.isalnum()):
            words.append(text)
            confs.append(conf)
    mean = sum(confs) / len(confs) if confs else 0.0
    return " ".join(words), round(mean, 1)


def ocr_frames(
    frames: list[tuple[str, float, Path]], language: str, tesseract_cmd: str = "tesseract"
) -> list[OcrResult]:
    results: list[OcrResult] = []
    seen: set[str] = set()
    for frame_id, ts, path in frames:
        text, conf = ocr_image(path, language, tesseract_cmd)
        norm = " ".join(text.lower().split())
        if len(norm) < 3 or norm in seen:
            continue
        seen.add(norm)
        results.append(OcrResult(f"O{len(results) + 1}", frame_id, ts, text, conf))
    return results
