"""Connected-account lifecycle: OAuth completion, token refresh, media listing,
ownership-checked resolution of pasted links, and disconnect/revocation."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.integrations import instagram as ig
from app.integrations import youtube as yt
from app.integrations.common import (
    IntegrationError,
    consume_oauth_state,
    create_oauth_state,
    decrypt_token,
    encrypt_token,
    get_http_client,
    pkce_pair,
)
from app.integrations.urls import parse_instagram_shortcode, parse_youtube_video_id
from app.models import Analysis, PlatformConnection

log = logging.getLogger(__name__)

PLATFORMS = ("instagram", "youtube")
_HASHTAG = re.compile(r"#(\w{1,100})", re.UNICODE)


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------- OAuth


def start_authorization(platform: str, settings: Settings) -> str:
    with get_http_client() as http:
        if platform == "instagram":
            client = ig.InstagramClient(http, settings)
            return client.authorize_url(create_oauth_state("instagram"))
        if platform == "youtube":
            yclient = yt.YouTubeClient(http, settings)
            verifier, challenge = pkce_pair()
            state = create_oauth_state("youtube", {"verifier": verifier})
            return yclient.authorize_url(state, challenge)
    raise IntegrationError("Unknown platform.", 404)


def _upsert(db: Session, platform: str, external_id: str, **fields: Any) -> PlatformConnection:
    conn = db.scalar(
        select(PlatformConnection).where(
            PlatformConnection.platform == platform, PlatformConnection.external_id == external_id
        )
    )
    if conn is None:
        conn = PlatformConnection(platform=platform, external_id=external_id)
        db.add(conn)
    for k, v in fields.items():
        setattr(conn, k, v)
    conn.token_issued_at = _now()
    db.commit()
    db.refresh(conn)
    return conn


def complete_authorization(
    db: Session, platform: str, code: str, state: str, settings: Settings
) -> PlatformConnection:
    payload = consume_oauth_state(state, platform)
    with get_http_client() as http:
        if platform == "instagram":
            client = ig.InstagramClient(http, settings)
            tok = client.exchange_code(code)
            profile = client.profile(tok.access_token)
            user_id = str(profile.get("user_id") or tok.user_id or profile.get("id"))
            return _upsert(
                db,
                "instagram",
                user_id,
                display_name="@" + str(profile.get("username", user_id)),
                account_meta={
                    "username": profile.get("username"),
                    "account_type": profile.get("account_type"),
                    "app_scoped_id": profile.get("id"),
                },
                scopes=tok.scopes,
                access_token_enc=encrypt_token(tok.access_token),
                refresh_token_enc=None,
                token_expires_at=tok.expires_at,
            )
        if platform == "youtube":
            yclient = yt.YouTubeClient(http, settings)
            ytok = yclient.exchange_code(code, str(payload.get("verifier", "")))
            channel = yclient.my_channel(ytok.access_token)
            snippet = channel.get("snippet") or {}
            uploads = ((channel.get("contentDetails") or {}).get("relatedPlaylists") or {}).get(
                "uploads"
            )
            return _upsert(
                db,
                "youtube",
                channel["id"],
                display_name=str(snippet.get("title") or channel["id"]),
                account_meta={"custom_url": snippet.get("customUrl"), "uploads_playlist": uploads},
                scopes=ytok.scopes,
                access_token_enc=encrypt_token(ytok.access_token),
                refresh_token_enc=encrypt_token(ytok.refresh_token) if ytok.refresh_token else None,
                token_expires_at=ytok.expires_at,
            )
    raise IntegrationError("Unknown platform.", 404)


def access_token(db: Session, conn: PlatformConnection, settings: Settings) -> str:
    """Return a valid access token, refreshing it when needed."""
    token = decrypt_token(conn.access_token_enc)
    now = _now()
    expires = conn.token_expires_at
    if conn.platform == "youtube":
        if expires is None or expires - now > timedelta(seconds=90):
            return token
        if not conn.refresh_token_enc:
            raise IntegrationError("YouTube session expired. Reconnect the channel.", 401)
        with get_http_client() as http:
            ref = yt.YouTubeClient(http, settings).refresh(decrypt_token(conn.refresh_token_enc))
        conn.access_token_enc = encrypt_token(ref.access_token)
        conn.token_expires_at = ref.expires_at
        db.commit()
        return ref.access_token
    # Instagram long-lived tokens: refresh when < 7 days remain (must be > 24h old).
    if expires is not None and expires <= now:
        raise IntegrationError("Instagram session expired. Reconnect the account.", 401)
    if (
        expires is not None
        and expires - now < timedelta(days=7)
        and now - conn.token_issued_at > timedelta(hours=24)
    ):
        with get_http_client() as http:
            ref_ig = ig.InstagramClient(http, settings).refresh(token)
        conn.access_token_enc = encrypt_token(ref_ig.access_token)
        conn.token_expires_at = ref_ig.expires_at
        conn.token_issued_at = now
        db.commit()
        return ref_ig.access_token
    return token


def disconnect(db: Session, conn: PlatformConnection, settings: Settings) -> int:
    """Revoke access where the platform supports it, then delete the connection and
    every analysis imported through it (YouTube policy requires deleting authorized
    data after revocation). Returns the number of analyses deleted."""
    from app.jobs import delete_analysis

    if conn.platform == "youtube":
        try:
            token = decrypt_token(conn.refresh_token_enc or conn.access_token_enc)
            with get_http_client() as http:
                yt.YouTubeClient(http, settings).revoke(token)
        except Exception:  # revocation is best effort; local deletion must still happen
            log.warning("YouTube token revocation failed for connection %s", conn.id)
    imported = db.scalars(select(Analysis).where(Analysis.connection_id == conn.id)).all()
    for a in imported:
        delete_analysis(db, a)
    db.delete(conn)
    db.commit()
    return len(imported)


# ---------------------------------------------------------------- media


def normalise_instagram(item: dict[str, Any]) -> dict[str, Any]:
    caption = item.get("caption") or ""
    return {
        "id": item["id"],
        "title": caption.split("\n")[0][:120] or "Untitled post",
        "caption": caption,
        "permalink": item.get("permalink"),
        "thumbnail_url": item.get("thumbnail_url") or item.get("media_url"),
        "published_at": item.get("timestamp"),
        "media_type": item.get("media_product_type") or item.get("media_type"),
        "duration_seconds": None,
        "privacy": None,
        "expected_mode": "full_video" if item.get("media_url") else "caption_thumbnail",
    }


def normalise_youtube(video: dict[str, Any]) -> dict[str, Any]:
    sn = video.get("snippet") or {}
    thumbs = sn.get("thumbnails") or {}
    thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url")
    return {
        "id": video["id"],
        "title": sn.get("title") or "Untitled video",
        "caption": sn.get("description") or "",
        "permalink": f"https://www.youtube.com/watch?v={video['id']}",
        "thumbnail_url": thumb,
        "published_at": sn.get("publishedAt"),
        "media_type": "VIDEO",
        "duration_seconds": yt.parse_iso_duration(
            (video.get("contentDetails") or {}).get("duration")
        ),
        "privacy": (video.get("status") or {}).get("privacyStatus"),
        "expected_mode": "metadata_only",
    }


def list_media(
    db: Session, conn: PlatformConnection, settings: Settings, cursor: str | None
) -> tuple[list[dict[str, Any]], str | None]:
    token = access_token(db, conn, settings)
    with get_http_client() as http:
        if conn.platform == "instagram":
            items, nxt = ig.InstagramClient(http, settings).media_page(
                conn.external_id, token, cursor
            )
            return [normalise_instagram(i) for i in items if ig.is_video(i)], nxt
        uploads = conn.account_meta.get("uploads_playlist")
        if not uploads:
            raise IntegrationError("Channel uploads playlist unknown. Reconnect the channel.", 409)
        videos, nxt = yt.YouTubeClient(http, settings).uploads_page(token, uploads, cursor)
        return [normalise_youtube(v) for v in videos], nxt


def resolve_media(
    db: Session,
    conn: PlatformConnection,
    settings: Settings,
    *,
    url: str | None = None,
    media_id: str | None = None,
) -> dict[str, Any]:
    """Find the requested item and verify it belongs to the connected account."""
    if not url and not media_id:
        raise IntegrationError("Provide a link or choose a post.", 422)
    token = access_token(db, conn, settings)
    with get_http_client() as http:
        if conn.platform == "instagram":
            client = ig.InstagramClient(http, settings)
            if url:
                code = parse_instagram_shortcode(url)

                def match(i: dict[str, Any]) -> bool:
                    link = i.get("permalink") or ""
                    return f"/{code}/" in link or link.rstrip("/").endswith("/" + code)
            else:

                def match(i: dict[str, Any]) -> bool:
                    return str(i.get("id")) == media_id

            item = client.find_own_media(conn.external_id, token, match)
            if item is None:
                pages = settings.instagram_media_scan_pages * 25
                raise IntegrationError(
                    f"That post was not found among the {pages} most recent posts of "
                    f"{conn.display_name}. Only your own posts can be analysed.",
                    403,
                )
            if not ig.is_video(item):
                raise IntegrationError("Only Reels and video posts can be analysed.", 422)
            return normalise_instagram(item)

        yclient = yt.YouTubeClient(http, settings)
        video_id = parse_youtube_video_id(url) if url else str(media_id)
        videos = yclient.videos(token, [video_id])
        if not videos:
            raise IntegrationError("Video not found (it may be private to another account).", 404)
        video = videos[0]
        if (video.get("snippet") or {}).get("channelId") != conn.external_id:
            raise IntegrationError(
                f"That video does not belong to {conn.display_name}. "
                "Only your own videos can be analysed.",
                403,
            )
        return normalise_youtube(video)


def hashtags_from_text(*texts: str) -> list[str]:
    tags: list[str] = []
    for t in texts:
        for tag in _HASHTAG.findall(t or ""):
            if tag not in tags:
                tags.append(tag)
    return tags
