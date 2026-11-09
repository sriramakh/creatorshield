"""Generate synthetic sample videos that this project owns outright.

Visuals are solid-colour slides rendered with Pillow; speech is macOS `say`
text-to-speech; the "music" bed is an FFmpeg sine chord. No third-party
footage, music or likeness is used, so the samples are safe to analyse,
commit and share.

Usage (from repo root):
    backend/.venv/bin/python samples/generate_samples.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parent
W, H = 720, 1280  # 9:16 vertical
LATIN_FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


@dataclass
class Slide:
    seconds: float
    bg: str
    lines: list[str]
    font: str = LATIN_FONT


@dataclass
class Sample:
    name: str
    voice: str
    speech: str
    slides: list[Slide]
    music_tail_seconds: float = 0.0  # non-speech tone appended at the end
    lead_in_seconds: float = 0.5


SAMPLES = [
    Sample(
        name="sample_promo_en",
        voice="Samantha",
        speech=(
            "Hey everyone, welcome back to my morning routine. "
            "First, a big glass of water and five minutes of stretching. "
            "Now, this FitFuel protein powder completely cured my back pain in just three days. "
            "Guaranteed results, doctors don't want you to know this. "
            "Use my code FIT50 for fifty percent off. The link is in my bio!"
        ),
        slides=[
            Slide(7, "#1e3a8a", ["MY MORNING", "ROUTINE"]),
            Slide(7, "#c2410c", ["CURED MY BACK PAIN", "IN 3 DAYS!"]),
            Slide(7, "#15803d", ["USE CODE FIT50", "50% OFF", "LINK IN BIO"]),
            Slide(6, "#111827", ["FOLLOW FOR", "MORE"]),
        ],
        music_tail_seconds=6.0,
    ),
    Sample(
        name="sample_tips_en",
        voice="Samantha",
        speech=(
            "Here are three simple stretches to do after a workout. "
            "One, a standing hamstring stretch for thirty seconds. "
            "Two, a gentle quad stretch, holding a wall for balance. "
            "Three, a child's pose to relax your lower back. "
            "If you feel sharp pain, stop and talk to a qualified professional."
        ),
        slides=[
            Slide(6, "#0f766e", ["3 STRETCHES", "AFTER A WORKOUT"]),
            Slide(6, "#334155", ["1. HAMSTRING", "30 SECONDS"]),
            Slide(6, "#4338ca", ["2. QUAD STRETCH"]),
            Slide(6, "#7c2d12", ["3. CHILD'S POSE"]),
        ],
    ),
    Sample(
        name="sample_promo_hi",
        voice="Lekha",
        speech=(
            "नमस्ते दोस्तों! आज मैं आपको अपना पसंदीदा स्किन केयर प्रोडक्ट दिखाने वाली हूँ। "
            "इस क्रीम से सिर्फ़ सात दिनों में चेहरा एकदम गोरा हो जाएगा, गारंटी है। "
            "मेरा कोड GLOW30 इस्तेमाल करें और तीस प्रतिशत छूट पाएं। लिंक बायो में है।"
        ),
        slides=[
            # Latin script on purpose: Pillow without libraqm cannot shape
            # Devanagari correctly, which would produce garbled OCR input.
            Slide(7, "#831843", ["MERA SKIN CARE", "ROUTINE"]),
            Slide(7, "#1e40af", ["CODE GLOW30", "30% OFF"]),
            Slide(6, "#065f46", ["LINK IN BIO"]),
        ],
    ),
]


def render_slide(slide: Slide, path: Path) -> None:
    img = Image.new("RGB", (W, H), slide.bg)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(slide.font, 64)
    heights = [draw.textbbox((0, 0), line, font=font)[3] for line in slide.lines]
    total = sum(heights) + 40 * (len(slide.lines) - 1)
    y = (H - total) / 2
    for line, h in zip(slide.lines, heights, strict=True):
        w = draw.textlength(line, font=font)
        draw.text(((W - w) / 2, y), line, font=font, fill="white")
        y += h + 40
    img.save(path)


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def build(sample: Sample, tmp: Path) -> Path:
    # 1. speech
    aiff = tmp / f"{sample.name}.aiff"
    run(["say", "-v", sample.voice, "-o", str(aiff), sample.speech])
    # 2. slides -> concat list
    concat = tmp / f"{sample.name}.txt"
    lines = []
    for i, slide in enumerate(sample.slides):
        png = tmp / f"{sample.name}_{i}.png"
        render_slide(slide, png)
        lines += [f"file '{png}'", f"duration {slide.seconds}"]
    lines.append(f"file '{tmp / f'{sample.name}_{len(sample.slides) - 1}.png'}'")
    concat.write_text("\n".join(lines) + "\n")
    video_seconds = sum(s.seconds for s in sample.slides)

    # 3. audio: lead-in silence + speech, optional sine "music" tail, padded to video length
    filters = [f"[0:a]adelay={int(sample.lead_in_seconds * 1000)}:all=1,aresample=44100[sp]"]
    inputs = ["-i", str(aiff)]
    mix_inputs = "[sp]"
    if sample.music_tail_seconds:
        start = video_seconds - sample.music_tail_seconds
        inputs += [
            "-f", "lavfi", "-i", f"sine=frequency=262:duration={sample.music_tail_seconds}",
            "-f", "lavfi", "-i", f"sine=frequency=330:duration={sample.music_tail_seconds}",
            "-f", "lavfi", "-i", f"sine=frequency=392:duration={sample.music_tail_seconds}",
        ]
        filters.append(
            "[1:a][2:a][3:a]amix=inputs=3,volume=0.6,"
            f"adelay={int(start * 1000)}:all=1,aresample=44100[mu]"
        )
        mix_inputs += "[mu]"
        filters.append(f"{mix_inputs}amix=inputs=2:normalize=0,apad[a]")
    else:
        filters.append("[sp]apad[a]")
    wav = tmp / f"{sample.name}.wav"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filters), "-map", "[a]",
         "-t", str(video_seconds), str(wav)])

    out = OUT_DIR / f"{sample.name}.mp4"
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(wav),
        "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k", "-t", str(video_seconds), "-movflags", "+faststart",
        str(out),
    ])
    return out


def main() -> int:
    if not shutil.which("say") or not shutil.which("ffmpeg"):
        print("requires macOS `say` and ffmpeg", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as d:
        for sample in SAMPLES:
            print("built", build(sample, Path(d)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
