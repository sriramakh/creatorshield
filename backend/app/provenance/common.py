"""Shared pieces for provenance lookups."""

from __future__ import annotations


class LookupFailed(Exception):
    """Expected failure of an optional lookup. ``user_message`` is safe to display."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message
