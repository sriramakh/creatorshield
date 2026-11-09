"""Instagram API with Instagram Login (professional accounts only).

Official endpoints only (developers.facebook.com/docs/instagram-platform):
authorize -> short-lived token -> long-lived token (60 days, refreshable),
GET /me, GET /<IG_ID>/media, GET /<IG_MEDIA_ID>.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.integrations.common import IntegrationError, raise_for_platform

PLATFORM = "Instagram"
SCOPES = ["instagram_business_basic"]
MEDIA_FIELDS = (
    "id,caption,media_type,media_product_type,media_url,permalink,thumbnail_url,timestamp"
)


@dataclass
class TokenResult:
    access_token: str
    user_id: str
    expires_at: datetime | None
    scopes: list[str]


class InstagramClient:
    def __init__(self, http: httpx.Client, settings: Settings) -> None:
        self.http = http
        self.s = settings
        if not settings.instagram_configured:
            raise IntegrationError(
                "Instagram is not configured (INSTAGRAM_APP_ID / INSTAGRAM_APP_SECRET).", 503
            )
        assert settings.instagram_app_secret is not None
        self._secret = settings.instagram_app_secret.get_secret_value()

    def _graph(self, path: str) -> str:
        return f"{self.s.instagram_graph_url.rstrip('/')}/{self.s.instagram_api_version}/{path}"

    # ---------------------------------------------------------------- OAuth
    def authorize_url(self, state: str) -> str:
        params = {
            "client_id": self.s.instagram_app_id,
            "redirect_uri": self.s.instagram_callback,
            "response_type": "code",
            "scope": ",".join(SCOPES),
            "state": state,
        }
        return f"{self.s.instagram_oauth_url}?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenResult:
        code = code.split("#")[0].strip()  # Instagram appends "#_" to the code
        short = raise_for_platform(
            self.http.post(
                self.s.instagram_token_url,
                data={
                    "client_id": self.s.instagram_app_id,
                    "client_secret": self._secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.s.instagram_callback,
                    "code": code,
                },
            ),
            PLATFORM,
        )
        record = short["data"][0] if isinstance(short.get("data"), list) else short
        short_token = record.get("access_token")
        if not short_token:
            raise IntegrationError("Instagram did not return an access token.", 502)
        perms = record.get("permissions") or SCOPES
        scopes = perms.split(",") if isinstance(perms, str) else list(perms)

        long = raise_for_platform(
            self.http.get(
                f"{self.s.instagram_graph_url.rstrip('/')}/access_token",
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": self._secret,
                    "access_token": short_token,
                },
            ),
            PLATFORM,
        )
        return TokenResult(
            access_token=long["access_token"],
            user_id=str(record.get("user_id", "")),
            expires_at=_expiry(long.get("expires_in")),
            scopes=scopes,
        )

    def refresh(self, access_token: str) -> TokenResult:
        body = raise_for_platform(
            self.http.get(
                f"{self.s.instagram_graph_url.rstrip('/')}/refresh_access_token",
                params={"grant_type": "ig_refresh_token", "access_token": access_token},
            ),
            PLATFORM,
        )
        return TokenResult(body["access_token"], "", _expiry(body.get("expires_in")), SCOPES)

    # ---------------------------------------------------------------- data
    def profile(self, access_token: str) -> dict[str, Any]:
        return raise_for_platform(
            self.http.get(
                self._graph("me"),
                params={"fields": "id,user_id,username,account_type", "access_token": access_token},
            ),
            PLATFORM,
        )

    def media_page(
        self, ig_user_id: str, access_token: str, after: str | None = None, limit: int = 25
    ) -> tuple[list[dict[str, Any]], str | None]:
        params = {"fields": MEDIA_FIELDS, "limit": str(limit), "access_token": access_token}
        if after:
            params["after"] = after
        body = raise_for_platform(
            self.http.get(self._graph(f"{ig_user_id}/media"), params=params), PLATFORM
        )
        items = body.get("data") or []
        paging = body.get("paging") or {}
        next_cursor = (paging.get("cursors") or {}).get("after") if paging.get("next") else None
        return items, next_cursor

    def iter_media(self, ig_user_id: str, access_token: str, max_pages: int) -> Iterator[dict]:
        after: str | None = None
        for _ in range(max_pages):
            items, after = self.media_page(ig_user_id, access_token, after)
            yield from items
            if not after:
                return

    def find_own_media(
        self, ig_user_id: str, access_token: str, match: Callable[[dict[str, Any]], bool]
    ) -> dict[str, Any] | None:
        """Ownership check: the item must appear in the connected account's own media."""
        for item in self.iter_media(ig_user_id, access_token, self.s.instagram_media_scan_pages):
            if match(item):
                return item
        return None

    def media(self, media_id: str, access_token: str) -> dict[str, Any]:
        """Fresh media details (CDN media_url values expire, so fetch right before download)."""
        return raise_for_platform(
            self.http.get(
                self._graph(media_id), params={"fields": MEDIA_FIELDS, "access_token": access_token}
            ),
            PLATFORM,
        )


def _expiry(expires_in: Any) -> datetime | None:
    try:
        return datetime.now(UTC) + timedelta(seconds=int(expires_in))
    except (TypeError, ValueError):
        return None


def is_video(item: dict[str, Any]) -> bool:
    return item.get("media_type") == "VIDEO" or item.get("media_product_type") == "REELS"
