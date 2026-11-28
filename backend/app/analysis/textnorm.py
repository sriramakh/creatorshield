"""Text normalisation shared by the rule-based checks.

Captions, transcripts and OCR arrive with typographic quotes, full-width
characters and invisible joiners (copied from phone keyboards or inserted to
dodge filters). Rule patterns are written for plain ASCII punctuation, so every
check normalises its input with :func:`normalise` before matching.
"""

from __future__ import annotations

import re
import unicodedata

# Zero-width and soft-hyphen characters that are invisible when rendered.
_INVISIBLE = re.compile("[­᠎​-‏‪-‮⁠-⁤﻿]")
# Typographic apostrophes and quotes -> ASCII.
_QUOTES = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "′": "'",
        "ʼ": "'",
        "`": "'",
        "´": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',
        "″": '"',
    }
)


def normalise(text: str) -> str:
    """NFKC, invisible characters removed, typographic quotes made ASCII."""
    text = unicodedata.normalize("NFKC", text or "")
    text = _INVISIBLE.sub("", text)
    return text.translate(_QUOTES)
