"""A fake Instagram Graph + Google OAuth/YouTube Data API server for tests.

It mimics only the official endpoints CreatorShield calls, so the OAuth and
import flows can be exercised end-to-end without real accounts or credentials.

    # standalone (browser E2E):
    FAKE_CDN_BASE=http://127.0.0.1:8099/cdn .venv/bin/uvicorn tests.fake_platforms:app --port 8099
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_VIDEO = Path(os.environ.get("FAKE_SAMPLE_VIDEO", ROOT / "samples" / "sample_promo_en.mp4"))
THUMBNAIL = Path(
    os.environ.get("FAKE_THUMBNAIL", Path(tempfile.gettempdir()) / "creatorshield_fake_thumb.jpg")
)
CDN_BASE = os.environ.get("FAKE_CDN_BASE", "https://scontent.cdninstagram.com/cdn")

IG_USER_ID = "17841400000000001"
IG_LONG_TOKEN = "IGLONG-fake-token"  # noqa: S105
YT_ACCESS = "YTACCESS-fake-token"  # noqa: S105
YT_REFRESH = "YTREFRESH-fake-token"  # noqa: S105
YT_CHANNEL = "UCdemoChannel000000000001"

# Mutable state inspected by tests.
STATE: dict[str, Any] = {"revoked": [], "token_requests": []}

app = FastAPI(title="fake platforms")


def _ig_media() -> list[dict[str, Any]]:
    return [
        {  # Reel with a downloadable file -> full analysis
            "id": "18000000000000001",
            "media_type": "VIDEO",
            "media_product_type": "REELS",
            "caption": "Morning routine with FitFuel! Use code FIT50 #fitness #protein",
            "media_url": f"{CDN_BASE}/reel1.mp4",
            "thumbnail_url": f"{CDN_BASE}/thumb1.jpg",
            "permalink": "https://www.instagram.com/reel/DEMOreel001/",
            "timestamp": "2026-10-20T10:00:00+0000",
        },
        {  # Reel with licensed audio -> Instagram omits media_url
            "id": "18000000000000002",
            "media_type": "VIDEO",
            "media_product_type": "REELS",
            "caption": "Glow up in 7 days, guaranteed ✨ link in bio #skincare",
            "thumbnail_url": f"{CDN_BASE}/thumb2.jpg",
            "permalink": "https://www.instagram.com/reel/DEMOreel002/",
            "timestamp": "2026-10-19T10:00:00+0000",
        },
        {  # Image post (not analysable as video)
            "id": "18000000000000003",
            "media_type": "IMAGE",
            "media_product_type": "FEED",
            "caption": "A photo",
            "media_url": f"{CDN_BASE}/photo.jpg",
            "permalink": "https://www.instagram.com/p/DEMOphoto03/",
            "timestamp": "2026-10-18T10:00:00+0000",
        },
        {  # Reel whose CDN URL redirects to a non-allow-listed host
            "id": "18000000000000004",
            "media_type": "VIDEO",
            "media_product_type": "REELS",
            "caption": "Redirect test",
            "media_url": f"{CDN_BASE}/redirect-evil.mp4",
            "permalink": "https://www.instagram.com/reel/DEMOreel004/",
            "timestamp": "2026-10-17T10:00:00+0000",
        },
    ]


def _ig_token(token: str | None) -> None:
    if token != IG_LONG_TOKEN:
        raise HTTPException(401, {"error": {"message": "Invalid OAuth access token"}})


# Registered first: the generic "/{version}/{media_id}" route would otherwise match.
@app.get("/cdn/{name}")
def cdn(name: str) -> Any:
    if name == "reel1.mp4":
        return FileResponse(SAMPLE_VIDEO, media_type="video/mp4")
    if name in ("thumb1.jpg", "thumb2.jpg", "photo.jpg"):
        return FileResponse(_thumbnail(), media_type="image/jpeg")
    if name == "redirect-evil.mp4":
        return RedirectResponse("https://evil.example.com/steal.mp4", status_code=302)
    raise HTTPException(404)


def _thumbnail() -> Path:
    """A real JPEG cut from the sample video (generated on first use)."""
    if not THUMBNAIL.exists():
        THUMBNAIL.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-ss",
                "8",
                "-i",
                str(SAMPLE_VIDEO),
                "-frames:v",
                "1",
                str(THUMBNAIL),
            ],
            check=True,
        )
    return THUMBNAIL


# ---------------------------------------------------------------- Instagram
@app.get("/oauth/authorize")
def ig_authorize(redirect_uri: str, state: str, client_id: str, scope: str) -> RedirectResponse:
    return RedirectResponse(f"{redirect_uri}?{urlencode({'code': 'IGCODE', 'state': state})}#_")


@app.post("/oauth/access_token")
def ig_short_token(code: str = Form(...), grant_type: str = Form(...)) -> dict[str, Any]:
    if code != "IGCODE" or grant_type != "authorization_code":
        raise HTTPException(400, {"error": {"message": "bad code"}})
    return {
        "data": [
            {
                "access_token": "IGSHORT",
                "user_id": IG_USER_ID,
                "permissions": "instagram_business_basic",
            }
        ]
    }


@app.get("/access_token")
def ig_long_token(grant_type: str, access_token: str) -> dict[str, Any]:
    if grant_type != "ig_exchange_token" or access_token != "IGSHORT":  # noqa: S105
        raise HTTPException(400, {"error": {"message": "bad exchange"}})
    return {"access_token": IG_LONG_TOKEN, "token_type": "bearer", "expires_in": 5184000}


@app.get("/refresh_access_token")
def ig_refresh(access_token: str) -> dict[str, Any]:
    _ig_token(access_token)
    return {"access_token": IG_LONG_TOKEN, "token_type": "bearer", "expires_in": 5184000}


@app.get("/{version}/me")
def ig_me(version: str, access_token: str) -> dict[str, Any]:
    _ig_token(access_token)
    return {
        "id": "app-scoped-1",
        "user_id": IG_USER_ID,
        "username": "creator_demo",
        "account_type": "MEDIA_CREATOR",
    }


@app.get("/{version}/{node_id}/media")
def ig_media_list(version: str, node_id: str, access_token: str) -> dict[str, Any]:
    _ig_token(access_token)
    if node_id != IG_USER_ID:
        raise HTTPException(403, {"error": {"message": "not your account"}})
    return {"data": _ig_media(), "paging": {"cursors": {"after": "END"}}}


@app.get("/{version}/{media_id}")
def ig_media_detail(version: str, media_id: str, access_token: str) -> dict[str, Any]:
    _ig_token(access_token)
    for item in _ig_media():
        if item["id"] == media_id:
            return item
    raise HTTPException(404, {"error": {"message": "media not found"}})


# ---------------------------------------------------------------- Google / YouTube
@app.get("/o/oauth2/v2/auth")
def google_authorize(redirect_uri: str, state: str, code_challenge: str, scope: str) -> Any:
    STATE["last_scope"] = scope
    return RedirectResponse(f"{redirect_uri}?{urlencode({'code': 'GCODE', 'state': state})}")


@app.post("/token")
def google_token(
    request: Request,
    grant_type: str = Form(...),
    code: str | None = Form(None),
    code_verifier: str | None = Form(None),
    refresh_token: str | None = Form(None),
) -> dict[str, Any]:
    STATE["token_requests"].append(grant_type)
    scope = STATE.get("last_scope", "https://www.googleapis.com/auth/youtube.readonly")
    if grant_type == "authorization_code":
        if code != "GCODE" or not code_verifier:
            raise HTTPException(400, {"error": "invalid_grant"})
        return {
            "access_token": YT_ACCESS,
            "refresh_token": YT_REFRESH,
            "expires_in": 3600,
            "scope": scope,
            "token_type": "Bearer",
        }
    if grant_type == "refresh_token" and refresh_token == YT_REFRESH:
        return {"access_token": YT_ACCESS, "expires_in": 3600, "scope": scope}
    raise HTTPException(400, {"error": "invalid_grant"})


@app.post("/revoke")
def google_revoke(token: str = Form(...)) -> dict[str, str]:
    STATE["revoked"].append(token)
    return {}


def _yt_auth(authorization: str | None) -> None:
    if authorization != f"Bearer {YT_ACCESS}":
        raise HTTPException(401, {"error": {"message": "Request had invalid authentication"}})


_VIDEOS = {
    "vidOwn00001": {
        "id": "vidOwn00001",
        "snippet": {
            "channelId": YT_CHANNEL,
            "title": "My morning routine 💪 #shorts",
            "description": "This protein cured my back pain in 3 days, guaranteed! "
            "Use code FIT50 for 50% off. Link in bio. #fitness #protein",
            "tags": ["fitness", "protein", "morning routine"],
            "publishedAt": "2026-10-20T10:00:00Z",
            "categoryId": "26",
            "thumbnails": {"medium": {"url": "https://i.ytimg.com/vi/vidOwn00001/mqdefault.jpg"}},
        },
        "contentDetails": {"duration": "PT27S"},
        "status": {"privacyStatus": "private", "madeForKids": False},
    },
    "vidOther001": {
        "id": "vidOther001",
        "snippet": {
            "channelId": "UCsomeoneElse000000000001",
            "title": "Not yours",
            "description": "",
            "publishedAt": "2026-10-01T10:00:00Z",
        },
        "contentDetails": {"duration": "PT45S"},
        "status": {"privacyStatus": "public"},
    },
}


@app.get("/youtube/v3/channels")
def yt_channels(mine: str, authorization: str | None = Header(None)) -> dict[str, Any]:
    _yt_auth(authorization)
    return {
        "items": [
            {
                "id": YT_CHANNEL,
                "snippet": {"title": "Demo Creator", "customUrl": "@democreator"},
                "contentDetails": {"relatedPlaylists": {"uploads": "UUdemo"}},
            }
        ]
    }


@app.get("/youtube/v3/playlistItems")
def yt_playlist(playlistId: str, authorization: str | None = Header(None)) -> dict[str, Any]:  # noqa: N803
    _yt_auth(authorization)
    return {"items": [{"contentDetails": {"videoId": "vidOwn00001"}}]}


@app.get("/youtube/v3/videos")
def yt_videos(id: str, authorization: str | None = Header(None)) -> dict[str, Any]:  # noqa: A002
    _yt_auth(authorization)
    return {"items": [_VIDEOS[i] for i in id.split(",") if i in _VIDEOS]}


@app.get("/youtube/v3/captions")
def yt_captions(videoId: str, authorization: str | None = Header(None)) -> dict[str, Any]:  # noqa: N803
    _yt_auth(authorization)
    return {
        "items": [
            {"id": "capASR", "snippet": {"language": "en", "trackKind": "asr"}},
            {"id": "capStd", "snippet": {"language": "en", "trackKind": "standard"}},
        ]
    }


@app.get("/youtube/v3/captions/{caption_id}")
def yt_caption_download(caption_id: str, authorization: str | None = Header(None)) -> Any:
    _yt_auth(authorization)
    if caption_id != "capStd":
        raise HTTPException(403, {"error": {"message": "forbidden"}})
    return PlainTextResponse(
        "1\n00:00:00,500 --> 00:00:06,000\nHey everyone, welcome to my morning routine.\n\n"
        "2\n00:00:07,200 --> 00:00:12,900\n"
        "This protein powder <i>cured</i> my back pain in 3 days.\n\n"
        "3\n00:00:13,800 --> 00:00:18,900\nUse my code FIT50 for fifty percent off.\n"
    )
