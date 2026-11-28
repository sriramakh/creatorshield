"""Shared pieces for provenance lookups."""

from __future__ import annotations

import httpx


class LookupFailed(Exception):
    """Expected failure of an optional lookup. ``user_message`` is safe to display."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


class ProviderMayHaveBilled(LookupFailed):
    """The request reached the provider but no usable answer came back (timeout while
    waiting, unreadable body). The provider may still have charged for it."""


def classify_http_error(exc: httpx.HTTPError, service: str) -> LookupFailed:
    """Connection never made -> nothing billed; anything later -> maybe billed."""
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.UnsupportedProtocol)):
        return LookupFailed(f"{service} is unreachable.")
    if isinstance(exc, httpx.TimeoutException):
        return ProviderMayHaveBilled(f"{service} did not answer in time.")
    return ProviderMayHaveBilled(f"{service} connection failed.")
