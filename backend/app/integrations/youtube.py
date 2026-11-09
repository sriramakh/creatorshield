"""YouTube Data API v3 via Google OAuth 2.0 (authorization code + PKCE).

Per the YouTube API Services Developer Policies, audiovisual content is never
downloaded or stored. We read metadata (title, description, tags, status) and,
only when the broader captions scope is enabled, caption tracks the user can edit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.integrations.common import IntegrationError, raise_for_platform

PLATFORM = "YouTube"
SCOPE_READONLY = "https://www.googleapis.com/auth/youtube.readonly"
SCOPE_CAPTIONS = "https://www.googleapis.com/auth/youtube.force-ssl"


@dataclass
class TokenResult:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scopes: list[str]


class YouTubeClient:
    def __init__(self, http: httpx.Client, settings: Settings) -> None:
        self.http = http
        self.s = settings
        if not settings.youtube_configured:
            raise IntegrationError(
                "YouTube is not configured (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET).", 503
            )
        assert settings.google_client_secret is not None
        self._secret = settings.google_client_secret.get_secret_value()

    # ---------------------------------------------------------------- OAuth
    def scopes(self) -> list[str]:
        return [SCOPE_READONLY] + ([SCOPE_CAPTIONS] if self.s.youtube_captions_scope else [])

    def authorize_url(self, state: str, code_challenge: str) -> str:
        params = {
            "client_id": self.s.google_client_id,
            "redirect_uri": self.s.youtube_callback,
            "response_type": "code",
            "scope": " ".join(self.scopes()),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.s.google_auth_url}?{urlencode(params)}"

    def _token_request(self, data: dict[str, str]) -> dict[str, Any]:
        data = {"client_id": self.s.google_client_id or "", "client_secret": self._secret, **data}
        return raise_for_platform(self.http.post(self.s.google_token_url, data=data), PLATFORM)

    def exchange_code(self, code: str, verifier: str) -> TokenResult:
        body = self._token_request(
            {
                "code": code,
                "redirect_uri": self.s.youtube_callback,
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            }
        )
        return _token(body)

    def refresh(self, refresh_token: str) -> TokenResult:
        body = self._token_request({"refresh_token": refresh_token, "grant_type": "refresh_token"})
        result = _token(body)
        result.refresh_token = result.refresh_token or refresh_token
        return result

    def revoke(self, token: str) -> None:
        # Revoking the refresh token also invalidates its access tokens.
        self.http.post(self.s.google_revoke_url, data={"token": token})

    # ---------------------------------------------------------------- data
    def _get(self, path: str, token: str, params: dict[str, str]) -> dict[str, Any]:
        return raise_for_platform(
            self.http.get(
                f"{self.s.youtube_api_url.rstrip('/')}/{path}",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            ),
            PLATFORM,
        )

    def my_channel(self, token: str) -> dict[str, Any]:
        items = (
            self._get("channels", token, {"part": "snippet,contentDetails", "mine": "true"}).get(
                "items"
            )
            or []
        )
        if not items:
            raise IntegrationError("This Google account has no YouTube channel.", 400)
        return items[0]

    def videos(self, token: str, video_ids: list[str]) -> list[dict[str, Any]]:
        if not video_ids:
            return []
        body = self._get(
            "videos", token, {"part": "snippet,contentDetails,status", "id": ",".join(video_ids)}
        )
        return body.get("items") or []

    def uploads_page(
        self, token: str, uploads_playlist: str, page_token: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        params = {"part": "contentDetails", "playlistId": uploads_playlist, "maxResults": "25"}
        if page_token:
            params["pageToken"] = page_token
        body = self._get("playlistItems", token, params)
        ids = [i["contentDetails"]["videoId"] for i in body.get("items") or []]
        return self.videos(token, ids), body.get("nextPageToken")

    def caption_tracks(self, token: str, video_id: str) -> list[dict[str, Any]]:
        return (
            self._get("captions", token, {"part": "snippet", "videoId": video_id}).get("items")
            or []
        )

    def download_caption(self, token: str, caption_id: str) -> str:
        resp = self.http.get(
            f"{self.s.youtube_api_url.rstrip('/')}/captions/{caption_id}",
            params={"tfmt": "srt"},
            headers={"Authorization": f"Bearer {token}"},
        )
        if not resp.is_success:
            raise_for_platform(resp, PLATFORM)
        return resp.text


def _token(body: dict[str, Any]) -> TokenResult:
    if not body.get("access_token"):
        raise IntegrationError("Google did not return an access token.", 502)
    expires = body.get("expires_in")
    return TokenResult(
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token"),
        expires_at=datetime.now(UTC) + timedelta(seconds=int(expires)) if expires else None,
        scopes=str(body.get("scope", "")).split(),
    )


_ISO_DURATION = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$")


def parse_iso_duration(value: str | None) -> float | None:
    m = _ISO_DURATION.match(value or "")
    if not m:
        return None
    d, h, mi, s = m.groups()
    return int(d or 0) * 86400 + int(h or 0) * 3600 + int(mi or 0) * 60 + float(s or 0)


_SRT_TIME = re.compile(r"(\d+):(\d{2}):(\d{2})[,.](\d{1,3})")


def _srt_seconds(stamp: str) -> float:
    m = _SRT_TIME.match(stamp.strip())
    if not m:
        raise ValueError(stamp)
    h, mi, s, ms = m.groups()
    return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def parse_srt(text: str) -> list[dict[str, Any]]:
    """SRT -> transcript segments in the same shape as speech-to-text output."""
    segments: list[dict[str, Any]] = []
    for block in re.split(r"\r?\n\s*\r?\n", text.strip()):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        timing = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if timing is None:
            continue
        try:
            start_s, end_s = (_srt_seconds(p) for p in lines[timing].split("-->"))
        except ValueError:
            continue
        body = " ".join(re.sub(r"<[^>]+>", "", ln).strip() for ln in lines[timing + 1 :]).strip()
        if body:
            segments.append(
                {
                    "id": f"T{len(segments) + 1}",
                    "start": round(start_s, 2),
                    "end": round(end_s, 2),
                    "text": body,
                }
            )
    return segments


def pick_caption_track(tracks: list[dict[str, Any]], language: str) -> dict[str, Any] | None:
    """Prefer a human-made track in the requested language, then any in that language.

    A track in another language is not a usable comparison: low word overlap
    would mark the creator's own file as a different cut.
    """
    want = language.lower().split("-")[0]

    def in_language(t: dict[str, Any]) -> bool:
        lang = str((t.get("snippet") or {}).get("language", "")).lower()
        return bool(want) and lang.split("-")[0] == want

    def human_track(t: dict[str, Any]) -> int:
        return int((t.get("snippet") or {}).get("trackKind") != "asr")

    matching = [t for t in tracks if in_language(t)]
    return max(matching, key=human_track) if matching else None
