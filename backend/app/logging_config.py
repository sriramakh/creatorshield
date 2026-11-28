from __future__ import annotations

import logging
import re

_MASK = "[REDACTED]"

# Values replaced outright wherever they appear.
_TOKEN_PATTERNS = [
    r"sk-[A-Za-z0-9_\-]{8,}",  # Anthropic / OpenAI keys
    r"proj-[A-Za-z0-9_\-]{16,}",  # bare OpenAI project keys
    r"AIza[0-9A-Za-z_\-]{30,}",  # Google API keys (YouTube, Vision)
    r"ya29\.[0-9A-Za-z_\-.]+",  # Google OAuth access tokens
    r"1//[0-9A-Za-z_\-]{20,}",  # Google OAuth refresh tokens
    r"\bIG[A-Za-z0-9_\-]{20,}",  # Instagram tokens (IGQ..., IGAA...)
    r"\bEAA[A-Za-z0-9]{20,}",  # Meta Graph tokens
    r"\bgAAAAA[A-Za-z0-9_\-=]{20,}",  # Fernet tokens (encrypted OAuth tokens)
    r"(?<![A-Za-z0-9_\-])[A-Za-z0-9_\-]{43}=(?![A-Za-z0-9_\-=])",  # Fernet keys
]
_TOKENS_RE = re.compile("|".join(f"(?:{p})" for p in _TOKEN_PATTERNS))
# Keep the label, mask the value.
_LABELLED_RE = re.compile(
    r"(?i)("
    r"\b(?:authorization|proxy-authorization)[\"']?\s*[:=]\s*[\"']?(?:basic|bearer|token)?\s*"
    # A credential after Basic/Bearer has 8+ token characters including a digit or
    # base64 punctuation (so "Basic information" in prose is left alone).
    r"|\b(?:basic|bearer)\s+(?=[A-Za-z0-9+/=._\-~]{8,})(?=[A-Za-z._\-~]*[0-9+/=])"
    r"|[?&;](?:key|api_key|access_token|refresh_token|client_secret|api_token|token|code"
    r"|password|signature|sig)="
    r"|[\"']?(?:access_token|refresh_token|client_secret|api_key|api_token|password"
    r"|token_encryption_key)[\"']?\s*[:=]\s*[\"']?"
    r")"
    r"([^\s\"'&,;}]+)"
)
# Passwords inside connection URLs (postgresql://user:password@host, redis://:pw@host).
_URL_PASSWORD_RE = re.compile(r"(\b[a-z][a-z0-9+.\-]*://[^:/@\s]*:)([^@/\s]+)(@)")


def redact(text: str) -> str:
    """Mask anything that looks like a credential. Idempotent."""
    if not text:
        return text
    text = _URL_PASSWORD_RE.sub(lambda m: m.group(1) + _MASK + m.group(3), text)
    text = _LABELLED_RE.sub(lambda m: m.group(1) + _MASK, text)
    return _TOKENS_RE.sub(_MASK, text)


class RedactSecrets(logging.Filter):
    """Defence in depth: mask credentials in log messages and exception text."""

    _formatter = logging.Formatter()

    def filter(self, record: logging.LogRecord) -> bool:
        # Redact arguments in place first so formatters that read record.args
        # (uvicorn's access formatter) keep working.
        if isinstance(record.args, tuple):
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {
                k: redact(v) if isinstance(v, str) else v for k, v in record.args.items()
            }
        try:
            msg = record.getMessage()
        except Exception:  # a malformed record must not break logging
            msg = str(record.msg)
        clean = redact(msg)
        if clean != msg:
            record.msg = clean
            record.args = ()
        if record.exc_info and not record.exc_text:
            record.exc_text = self._formatter.formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        if record.stack_info:
            record.stack_info = redact(record.stack_info)
        return True


class RedactingFormatter(logging.Formatter):
    """Redacts the fully formatted line, including tracebacks."""

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if getattr(root, "_creatorshield_configured", False):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(RedactSecrets())
    root.addHandler(handler)
    root.setLevel(level.upper())
    for noisy in ("httpx", "httpx2", "httpcore", "faster_whisper", "huggingface_hub"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # uvicorn and RQ install their own handlers; redact those too (access lines
    # carry query strings such as OAuth ?code=...).
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "rq.worker"):
        for h in logging.getLogger(name).handlers:
            if not any(isinstance(f, RedactSecrets) for f in h.filters):
                h.addFilter(RedactSecrets())
    root._creatorshield_configured = True  # type: ignore[attr-defined]
