"""Shared pieces for platform integrations: HTTP client, token encryption, OAuth state."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from typing import Any

import httpx
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class IntegrationError(Exception):
    """Expected failure talking to a platform. ``user_message`` is safe to display."""

    def __init__(self, user_message: str, status_code: int = 400) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.status_code = status_code


def get_http_client() -> httpx.Client:
    """Factory so tests can substitute a client wired to a fake platform server."""
    return httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=False)


def raise_for_platform(response: httpx.Response, platform: str) -> dict[str, Any]:
    """Return the JSON body or raise an IntegrationError without leaking tokens."""
    try:
        body: Any = response.json()
    except ValueError:
        body = {}
    if response.is_success:
        return body if isinstance(body, dict) else {"data": body}
    message = ""
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            message = str(err.get("message", ""))[:200]
        elif isinstance(err, str):
            message = str(body.get("error_description") or err)[:200]
    if response.status_code in (401, 403):
        detail = f"{platform} denied access ({response.status_code}). Reconnect the account."
        raise IntegrationError(f"{detail} {message}".strip(), 403)
    raise IntegrationError(f"{platform} API error ({response.status_code}). {message}".strip(), 502)


# ---------------------------------------------------------------- encryption


def _fernet() -> Fernet:
    key = get_settings().token_encryption_key
    if key is None or not key.get_secret_value():
        raise IntegrationError(
            "TOKEN_ENCRYPTION_KEY is not configured; connected accounts are disabled.", 503
        )
    return Fernet(key.get_secret_value().encode())


def encrypt_token(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise IntegrationError(
            "Stored token could not be decrypted (encryption key changed?). Reconnect the account.",
            409,
        ) from exc


def generate_encryption_key() -> str:
    return Fernet.generate_key().decode()


# ---------------------------------------------------------------- OAuth state (CSRF + PKCE)

_STATE_PREFIX = "creatorshield:oauth-state:"


def _redis():  # type: ignore[no-untyped-def]
    from app.jobs import get_redis

    return get_redis()


def create_oauth_state(platform: str, extra: dict[str, Any] | None = None) -> str:
    state = secrets.token_urlsafe(32)
    payload = {"platform": platform, **(extra or {})}
    _redis().set(
        _STATE_PREFIX + state, json.dumps(payload), ex=get_settings().oauth_state_ttl_seconds
    )
    return state


def consume_oauth_state(state: str, platform: str) -> dict[str, Any]:
    """Single-use: the state is deleted as it is read."""
    if not state or len(state) > 200:
        raise IntegrationError("Invalid OAuth state.", 400)
    raw = _redis().getdel(_STATE_PREFIX + state)
    if raw is None:
        raise IntegrationError("OAuth state expired or already used. Please try again.", 400)
    payload: dict[str, Any] = json.loads(raw)
    if payload.get("platform") != platform:
        raise IntegrationError("OAuth state does not match this platform.", 400)
    return payload


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode()
    return verifier, challenge.rstrip("=")
