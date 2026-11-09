"""Third-party content cues read from on-screen text (free, no external calls).

These are leads, not verdicts: a broadcaster name on screen can be a reaction
video with commentary, and OCR misreads stylised lettering.
"""

from __future__ import annotations

import re
from typing import Any

_HANDLE = re.compile(r"(?<![\w@.])@([A-Za-z0-9._]{3,30})")

# Broadcasters, studios, labels and streaming services whose footage or music is
# commonly reposted by Indian and global short-form accounts. Matched on OCR text
# only (what is visibly burned into the frame), never on speech.
BROADCASTERS = [
    "Star Sports",
    "Sony Sports",
    "Sony Ten",
    "SonyLIV",
    "Sony LIV",
    "Sony Max",
    "Sony SAB",
    "Zee TV",
    "ZEE5",
    "Zee Music",
    "Zee News",
    "Colors TV",
    "JioCinema",
    "Jio Cinema",
    "JioHotstar",
    "Hotstar",
    "Disney+",
    "Netflix",
    "Prime Video",
    "Amazon Prime",
    "T-Series",
    "TSeries",
    "Saregama",
    "Tips Music",
    "Sony Music",
    "Yash Raj Films",
    "YRF",
    "Dharma Productions",
    "Eros Now",
    "Aaj Tak",
    "ABP News",
    "NDTV",
    "India Today",
    "Republic TV",
    "Times Now",
    "DD News",
    "Doordarshan",
    "ESPN",
    "Sky Sports",
    "beIN Sports",
    "Fox Sports",
    "HBO",
    "BBC",
    "CNN",
    "WWE",
    "FanCode",
]
_BROADCASTER_RE = [
    (name, re.compile(r"(?<![\w])" + re.escape(name) + r"(?![\w])", re.IGNORECASE))
    for name in BROADCASTERS
]
_RIGHTS_NOTICE = re.compile(r"(©|\(c\)\s*\d{4}|all rights reserved|copyright\s+\d{4})", re.I)


def find_handles(ocr: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Distinct @handles visible on screen, with the first frame each appears in."""
    seen: dict[str, dict[str, Any]] = {}
    for item in ocr:
        for match in _HANDLE.finditer(str(item.get("text") or "")):
            handle = match.group(1).rstrip(".").lower()
            if len(handle) < 3 or handle in seen:
                continue
            seen[handle] = {
                "handle": "@" + handle,
                "ref_id": item["id"],
                "timestamp": item.get("timestamp"),
                "text": str(item.get("text") or "")[:160],
            }
    return list(seen.values())


def find_broadcasters(ocr: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for item in ocr:
        text = str(item.get("text") or "")
        for name, pattern in _BROADCASTER_RE:
            if name.casefold() in seen:
                continue
            if pattern.search(text):
                seen[name.casefold()] = {
                    "name": name,
                    "ref_id": item["id"],
                    "timestamp": item.get("timestamp"),
                    "text": text[:160],
                }
        if _RIGHTS_NOTICE.search(text) and "rights notice" not in seen:
            seen["rights notice"] = {
                "name": "Copyright notice",
                "ref_id": item["id"],
                "timestamp": item.get("timestamp"),
                "text": text[:160],
            }
    return list(seen.values())
