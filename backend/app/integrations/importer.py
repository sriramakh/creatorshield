"""Worker-side preparation of imported analyses.

Instagram: download the creator's own Reel via the official media_url (host
allow-listed, size-capped) for a full analysis; Instagram withholds media_url
for videos with licensed audio or copyright flags, in which case the caption and
thumbnail are analysed instead.

YouTube: metadata (+ captions when permitted) only. The YouTube API policies
forbid downloading audiovisual content, so no video or thumbnail is stored.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy.orm import Session

from app.config import Settings
from app.integrations import instagram as ig
from app.integrations import youtube as yt
from app.integrations.common import IntegrationError, get_http_client
from app.integrations.connections import access_token, hashtags_from_text
from app.media.ocr import ocr_frames, ocr_image
from app.media.probe import MediaError, probe
from app.models import Analysis, PlatformConnection
from app.storage import analysis_prefix, get_storage

log = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 15 * 1024 * 1024
ALLOWED_LOCAL_TEST_HOSTS = {"127.0.0.1", "localhost"}


def host_allowed(url: str, allowed: list[str]) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "http":
        # Plain HTTP only for explicitly allow-listed local hosts (test fakes).
        return host in ALLOWED_LOCAL_TEST_HOSTS and host in allowed
    if parsed.scheme != "https":
        return False
    return any(host == a or host.endswith("." + a) for a in allowed)


def download(
    http: httpx.Client, url: str, dest: Path, *, allowed: list[str], max_bytes: int, kind: str
) -> int:
    """Stream ``url`` to ``dest``. Every redirect hop is re-checked against the allow-list."""
    for _ in range(4):
        if not host_allowed(url, allowed):
            raise IntegrationError("Refusing to download media from an unexpected host.", 502)
        with http.stream("GET", url) as resp:
            if resp.is_redirect:
                url = urljoin(url, resp.headers.get("location", ""))
                continue
            if not resp.is_success:
                raise IntegrationError(f"Media download failed ({resp.status_code}).", 502)
            ctype = resp.headers.get("content-type", "")
            if not ctype.startswith(kind + "/"):
                raise IntegrationError(f"Unexpected media type from platform ({ctype}).", 502)
            written = 0
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as out:
                for chunk in resp.iter_bytes(1024 * 1024):
                    written += len(chunk)
                    if written > max_bytes:
                        out.close()
                        dest.unlink(missing_ok=True)
                        raise IntegrationError("Media file is larger than the allowed size.", 413)
                    out.write(chunk)
            return written
    raise IntegrationError("Too many redirects while downloading media.", 502)


def trim(video: Path, seconds: float) -> None:
    tmp = video.with_name("trimmed" + video.suffix)
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-t",
            f"{seconds:.2f}",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(tmp),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0 or not tmp.exists():
        raise MediaError("Could not trim the imported video.")
    tmp.replace(video)


def thumbnail_to_frame(image: Path, frame: Path) -> None:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(image),
            "-frames:v",
            "1",
            "-vf",
            "scale='min(768,iw)':-2",
            "-q:v",
            "4",
            str(frame),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    image.unlink(missing_ok=True)
    if proc.returncode != 0 or not frame.exists():
        raise MediaError("Could not read the post thumbnail.")


def prepare_owner_review(db: Session, analysis: Analysis, settings: Settings) -> dict[str, Any]:
    """Refresh the published post's metadata and normalise the creator's own file.

    Does not download the platform's video or audio. YouTube thumbnails are not
    stored. An Instagram cover image is read for text, then discarded.
    """
    conn = db.get(PlatformConnection, analysis.connection_id) if analysis.connection_id else None
    if conn is None:
        raise IntegrationError(
            "The connected account was removed. Reconnect and import again.", 409
        )
    if not analysis.storage_key:
        raise MediaError("The original video file is missing. Attach it again.")
    storage = get_storage()
    path = storage.local_path(analysis.storage_key)
    if not path.exists():
        raise MediaError("The original video file is no longer available. Attach it again.")

    token = access_token(db, conn, settings)
    with get_http_client() as http:
        if conn.platform == "instagram":
            snapshot = _instagram_snapshot(analysis, settings, http, token)
        elif conn.platform == "youtube":
            snapshot = _youtube_snapshot(analysis, settings, http, token, conn)
        else:
            raise IntegrationError("This account cannot be cross-checked.", 422)

    info = probe(path)
    original = info.duration_seconds
    notes: list[str] = []
    if original > settings.import_max_seconds + settings.duration_tolerance_seconds:
        trim(path, settings.import_max_seconds)
        info = probe(path)
        analysis.size_bytes = path.stat().st_size
        notes.append(
            f"The file is {original:.0f}s long; only the first "
            f"{settings.import_max_seconds:.0f}s were analysed."
        )
    analysis.analysis_mode = "cross_checked"
    analysis.media_info = info.to_dict()
    analysis.duration_seconds = info.duration_seconds
    analysis.limitations = notes
    snapshot["original_file_duration_seconds"] = original
    snapshot["analysed_duration_seconds"] = info.duration_seconds
    db.commit()
    return snapshot


def _instagram_snapshot(
    analysis: Analysis, settings: Settings, http: httpx.Client, token: str
) -> dict[str, Any]:
    item = ig.InstagramClient(http, settings).media(str(analysis.source_media_id), token)
    if not ig.is_video(item):
        raise IntegrationError("This Instagram post is not a video.", 422)
    analysis.caption = item.get("caption") or ""
    analysis.hashtags = hashtags_from_text(analysis.caption)
    analysis.source_url = item.get("permalink") or analysis.source_url
    analysis.source_title = (analysis.caption.split("\n")[0] or analysis.source_title or "")[:300]
    offered = bool(item.get("media_url"))
    warnings: list[str] = []
    thumbnail_text = ""
    thumb = item.get("thumbnail_url")
    if thumb:
        storage = get_storage()
        work = storage.local_path(analysis_prefix(analysis.id))
        raw = work / "cover.src"
        frame = work / "cover.jpg"
        try:
            download(
                http,
                thumb,
                raw,
                allowed=settings.import_media_hosts,
                max_bytes=MAX_IMAGE_BYTES,
                kind="image",
            )
            thumbnail_to_frame(raw, frame)
            thumbnail_text, _confidence = ocr_image(
                frame, analysis.language, settings.tesseract_cmd
            )
        except (IntegrationError, MediaError) as exc:
            warnings.append(f"The cover image could not be read: {exc}")
        finally:
            raw.unlink(missing_ok=True)
            frame.unlink(missing_ok=True)
    return {
        "platform_duration_seconds": None,
        "platform_withheld_media": not offered,
        "platform_offered_file": offered,
        "caption_segments": [],
        "thumbnail_text": thumbnail_text,
        "warnings": warnings,
        "source_metadata": {
            "permalink": item.get("permalink"),
            "media_type": item.get("media_product_type") or item.get("media_type"),
            "media_file_provided_by_platform": offered,
        },
    }


def _youtube_snapshot(
    analysis: Analysis,
    settings: Settings,
    http: httpx.Client,
    token: str,
    conn: PlatformConnection,
) -> dict[str, Any]:
    client = yt.YouTubeClient(http, settings)
    videos = client.videos(token, [str(analysis.source_media_id)])
    if not videos or (videos[0].get("snippet") or {}).get("channelId") != conn.external_id:
        raise IntegrationError("The video is no longer available on the connected channel.", 404)
    video = videos[0]
    sn = video.get("snippet") or {}
    status = video.get("status") or {}
    title, description = sn.get("title") or "", sn.get("description") or ""
    analysis.source_title = title[:300]
    analysis.caption = f"{title}\n\n{description}".strip()
    analysis.hashtags = hashtags_from_text(title, description)
    warnings = [
        "Frames, speech and audio in this review come from the file you supplied. "
        "YouTube's API policies do not allow downloading them from YouTube."
    ]
    segments: list[dict[str, Any]] = []
    if yt.SCOPE_CAPTIONS in conn.scopes:
        try:
            tracks = client.caption_tracks(token, video["id"])
            track = yt.pick_caption_track(tracks, analysis.language)
            if track:
                segments = yt.parse_srt(client.download_caption(token, track["id"]))
            elif tracks:
                warnings.append(
                    "No caption track in the requested language "
                    f"({analysis.language}) was available to compare with the file."
                )
            else:
                warnings.append("The video has no caption tracks to compare with the file.")
        except IntegrationError as exc:
            warnings.append(f"Captions could not be retrieved: {exc.user_message}")
    else:
        warnings.append(
            "Captions were not compared: the captions permission "
            "(youtube.force-ssl) is not enabled."
        )
    return {
        "platform_duration_seconds": yt.parse_iso_duration(
            (video.get("contentDetails") or {}).get("duration")
        ),
        "platform_withheld_media": False,
        "platform_offered_file": False,
        "caption_segments": segments,
        "thumbnail_text": "",
        "warnings": warnings,
        "source_metadata": {
            "title": title,
            "tags": (sn.get("tags") or [])[:100],
            "privacy_status": status.get("privacyStatus"),
            "made_for_kids": status.get("madeForKids"),
            "category_id": sn.get("categoryId"),
            "published_at": sn.get("publishedAt"),
        },
    }


def prepare_import(db: Session, analysis: Analysis, settings: Settings) -> dict[str, Any] | None:
    """Fetch source content. Returns a prebuilt extraction for non-video modes,
    or None when a video file was stored for the normal extraction pipeline."""
    conn = db.get(PlatformConnection, analysis.connection_id) if analysis.connection_id else None
    if conn is None:
        raise IntegrationError(
            "The connected account was removed. Reconnect and import again.", 409
        )
    token = access_token(db, conn, settings)
    analysis.limitations = []
    with get_http_client() as http:
        if conn.platform == "instagram":
            return _prepare_instagram(db, analysis, settings, http, token)
        return _prepare_youtube(analysis, settings, http, token, conn)


def _prepare_instagram(
    db: Session, analysis: Analysis, settings: Settings, http: httpx.Client, token: str
) -> dict[str, Any] | None:
    item = ig.InstagramClient(http, settings).media(str(analysis.source_media_id), token)
    analysis.caption = item.get("caption") or ""
    analysis.hashtags = hashtags_from_text(analysis.caption)
    analysis.source_url = item.get("permalink") or analysis.source_url
    storage = get_storage()
    prefix = analysis_prefix(analysis.id)
    work = storage.local_path(prefix)

    media_url = item.get("media_url")
    if media_url and ig.is_video(item):
        key = f"{prefix}/video.mp4"
        path = storage.local_path(key)
        size = download(
            http,
            media_url,
            path,
            allowed=settings.import_media_hosts,
            max_bytes=settings.max_upload_bytes,
            kind="video",
        )
        info = probe(path)
        notes: list[str] = []
        if (
            info.duration_seconds
            > settings.import_max_seconds + settings.duration_tolerance_seconds
        ):
            original = info.duration_seconds
            trim(path, settings.import_max_seconds)
            info = probe(path)
            size = path.stat().st_size
            notes.append(
                f"The Reel is {original:.0f}s long; only the first "
                f"{settings.import_max_seconds:.0f}s were analysed."
            )
        analysis.analysis_mode = "full_video"
        analysis.storage_key, analysis.file_ext, analysis.content_type = key, ".mp4", "video/mp4"
        analysis.size_bytes = size
        analysis.media_info = info.to_dict()
        analysis.duration_seconds = info.duration_seconds
        analysis.limitations = notes
        db.commit()
        return None

    # Instagram withheld the file -> analyse caption + thumbnail only.
    analysis.analysis_mode = "caption_thumbnail"
    analysis.duration_seconds = None
    analysis.media_info = None
    frames: list[dict[str, Any]] = []
    ocr: list[dict[str, Any]] = []
    warnings = [
        "Instagram did not provide the video file through its API. Instagram withholds the "
        "file for videos that contain licensed audio (including tracks from Instagram's "
        "audio library) or that were flagged for copyright, so only the caption and "
        "thumbnail were analysed. The reason for this post is not disclosed by Instagram."
    ]
    thumb = item.get("thumbnail_url")
    if thumb:
        try:
            raw = work / "frames" / "thumb.src"
            download(
                http,
                thumb,
                raw,
                allowed=settings.import_media_hosts,
                max_bytes=MAX_IMAGE_BYTES,
                kind="image",
            )
            frame = work / "frames" / "F1.jpg"
            thumbnail_to_frame(raw, frame)
            frames = [{"id": "F1", "timestamp": 0.0, "reason": "thumbnail", "file": "F1.jpg"}]
            if settings.ocr_enabled:
                ocr = [
                    {
                        "id": o.id,
                        "frame_id": o.frame_id,
                        "timestamp": o.timestamp,
                        "text": o.text,
                        "mean_confidence": o.mean_confidence,
                    }
                    for o in ocr_frames(
                        [("F1", 0.0, frame)], analysis.language, settings.tesseract_cmd
                    )
                ]
        except (IntegrationError, MediaError) as exc:
            warnings.append(f"Thumbnail could not be analysed: {exc}")
    db.commit()
    return {
        "transcript": {"provider": "none", "segments": []},
        "audio": None,
        "frames": frames,
        "ocr": ocr,
        "warnings": warnings,
    }


def _prepare_youtube(
    analysis: Analysis, settings: Settings, http: httpx.Client, token: str, conn: PlatformConnection
) -> dict[str, Any]:
    client = yt.YouTubeClient(http, settings)
    videos = client.videos(token, [str(analysis.source_media_id)])
    if not videos or (videos[0].get("snippet") or {}).get("channelId") != conn.external_id:
        raise IntegrationError("The video is no longer available on the connected channel.", 404)
    video = videos[0]
    sn = video.get("snippet") or {}
    status = video.get("status") or {}
    title, description = sn.get("title") or "", sn.get("description") or ""
    analysis.analysis_mode = "metadata_only"
    analysis.source_title = title[:300]
    analysis.caption = f"{title}\n\n{description}".strip()
    analysis.hashtags = hashtags_from_text(title, description)
    analysis.duration_seconds = yt.parse_iso_duration(
        (video.get("contentDetails") or {}).get("duration")
    )
    analysis.media_info = None

    warnings = [
        "YouTube's API policies do not allow downloading video or audio, so frames, speech "
        "and on-screen text were NOT analysed — only the title, description, tags and "
        "(when permitted) captions. Upload the video file for a full analysis."
    ]
    segments: list[dict[str, Any]] = []
    provider = "none"
    if yt.SCOPE_CAPTIONS in conn.scopes:
        try:
            tracks = client.caption_tracks(token, video["id"])
            track = yt.pick_caption_track(tracks, analysis.language)
            if track:
                segments = yt.parse_srt(client.download_caption(token, track["id"]))
                kind = (track.get("snippet") or {}).get("trackKind", "")
                provider = "youtube_captions_asr" if kind == "asr" else "youtube_captions"
            elif tracks:
                warnings.append(
                    "No caption track in the requested language "
                    f"({analysis.language}) was available to analyse."
                )
            else:
                warnings.append("The video has no caption tracks to analyse.")
        except IntegrationError as exc:
            warnings.append(f"Captions could not be retrieved: {exc.user_message}")
    else:
        warnings.append(
            "Captions were not read: the captions permission (youtube.force-ssl) is not enabled."
        )
    return {
        "transcript": {
            "provider": provider,
            "model": None,
            "language": analysis.language,
            "language_probability": None,
            "segments": segments,
        },
        "audio": None,
        "frames": [],
        "ocr": [],
        "warnings": warnings,
        "source_metadata": {
            "title": title,
            "tags": (sn.get("tags") or [])[:100],
            "privacy_status": status.get("privacyStatus"),
            "made_for_kids": status.get("madeForKids"),
            "category_id": sn.get("categoryId"),
            "published_at": sn.get("publishedAt"),
        },
    }
