from __future__ import annotations

import logging
import re

# Anthropic (sk-ant-...), OpenAI (sk-..., sk-proj-...) and bare project keys.
_SECRET_RE = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|proj-[A-Za-z0-9_\-]{16,})")


class RedactSecrets(logging.Filter):
    """Defence in depth: mask anything that looks like an API key in log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if _SECRET_RE.search(msg):
            record.msg = _SECRET_RE.sub("[REDACTED]", msg)
            record.args = ()
        return True


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if getattr(root, "_creatorshield_configured", False):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(RedactSecrets())
    root.addHandler(handler)
    root.setLevel(level.upper())
    for noisy in ("httpx", "httpx2", "httpcore", "faster_whisper", "huggingface_hub"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    root._creatorshield_configured = True  # type: ignore[attr-defined]
