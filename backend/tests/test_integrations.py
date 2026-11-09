"""Connected accounts + import flows against the fake platform server (no real APIs)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.db import get_sessionmaker
from app.integrations import common
from app.integrations.common import IntegrationError
from app.integrations.importer import host_allowed
from app.integrations.urls import parse_instagram_shortcode, parse_youtube_video_id
from app.integrations.youtube import parse_iso_duration, parse_srt, pick_caption_track
from app.main import app
from app.models import Analysis, PlatformConnection
from tests import fake_platforms

# ---------------------------------------------------------------- unit tests


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10", "dQw4w9WgXcQ"),
        ("youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?si=abc", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ],
)
def test_parse_youtube_urls(url: str, expected: str) -> None:
    assert parse_youtube_video_id(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch?v=short",
        "javascript:alert(1)",
        "https://youtube.com.evil.com/shorts/dQw4w9WgXcQ",
    ],
)
def test_parse_youtube_rejects(url: str) -> None:
    with pytest.raises(IntegrationError):
        parse_youtube_video_id(url)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.instagram.com/reel/DEMOreel001/", "DEMOreel001"),
        ("instagram.com/reels/DEMOreel001?igsh=x", "DEMOreel001"),
        ("https://www.instagram.com/creator_demo/reel/DEMOreel001/", "DEMOreel001"),
        ("https://www.instagram.com/p/DEMOphoto03/", "DEMOphoto03"),
    ],
)
def test_parse_instagram_urls(url: str, expected: str) -> None:
    assert parse_instagram_shortcode(url) == expected


def test_parse_instagram_rejects_other_hosts() -> None:
    with pytest.raises(IntegrationError):
        parse_instagram_shortcode("https://instagram.com.evil.io/reel/ABCDE/")


def test_media_host_allow_list() -> None:
    allowed = ["cdninstagram.com", "fbcdn.net"]
    assert host_allowed("https://scontent-bom1-1.cdninstagram.com/v/x.mp4", allowed)
    assert host_allowed("https://video.xx.fbcdn.net/v/x.mp4", allowed)
    assert not host_allowed("http://scontent.cdninstagram.com/x.mp4", allowed)  # not https
    assert not host_allowed("https://cdninstagram.com.evil.io/x.mp4", allowed)
    assert not host_allowed("https://169.254.169.254/latest/meta-data", allowed)
    assert not host_allowed("file:///etc/passwd", allowed)


def test_srt_duration_and_track_selection() -> None:
    segs = parse_srt(
        "1\n00:00:01,000 --> 00:00:02,500\n<b>Hello</b>\nthere\n\n2\nbad\n\n"
        "3\n00:01:00.250 --> 00:01:03,000\nBye\n"
    )
    assert segs == [
        {"id": "T1", "start": 1.0, "end": 2.5, "text": "Hello there"},
        {"id": "T2", "start": 60.25, "end": 63.0, "text": "Bye"},
    ]
    assert parse_iso_duration("PT1M3S") == 63 and parse_iso_duration("PT27S") == 27
    assert parse_iso_duration("garbage") is None
    tracks = [
        {"id": "a", "snippet": {"language": "en", "trackKind": "asr"}},
        {"id": "b", "snippet": {"language": "hi", "trackKind": "standard"}},
        {"id": "c", "snippet": {"language": "en-GB", "trackKind": "standard"}},
    ]
    assert pick_caption_track(tracks, "en")["id"] == "c"  # type: ignore[index]
    assert pick_caption_track(tracks, "hi")["id"] == "b"  # type: ignore[index]
    assert pick_caption_track(tracks, "ta") is None
    assert pick_caption_track([], "en") is None


def test_token_encryption_roundtrip() -> None:
    ct = common.encrypt_token("secret-token-value")
    assert "secret-token-value" not in ct
    assert common.decrypt_token(ct) == "secret-token-value"


# ---------------------------------------------------------------- flow tests


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    fake_platforms.STATE.update({"revoked": [], "token_requests": []})
    fake_platforms.STATE.pop("last_scope", None)

    def factory() -> TestClient:
        return TestClient(fake_platforms.app, follow_redirects=False)

    monkeypatch.setattr("app.integrations.connections.get_http_client", factory)
    monkeypatch.setattr("app.integrations.importer.get_http_client", factory)
    yield fake_platforms.STATE


@pytest.fixture
def api() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def connect(api: TestClient, platform: str, code: str) -> str:
    """Simulate the browser: our authorize URL -> platform consent page -> our callback."""
    auth = api.post(f"/api/connections/{platform}/authorize").json()["authorization_url"]
    consent = TestClient(fake_platforms.app, follow_redirects=False).get(auth)
    assert consent.status_code in (302, 307), consent.text
    back = urlparse(consent.headers["location"])
    params = parse_qs(back.query)
    assert params["code"] == [code.split("#")[0]]
    r = api.get(
        f"/api/connections/{platform}/callback",
        params={"code": code, "state": params["state"][0]},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    loc = urlparse(r.headers["location"])
    params = parse_qs(loc.query)
    assert loc.path == "/connections" and params["connected"] == [platform], r.headers["location"]
    return params["id"][0]


def import_(api: TestClient, conn_id: str, **body: str):  # type: ignore[no-untyped-def]
    return api.post("/api/analyses/import", json={"connection_id": conn_id, **body})


def test_oauth_state_is_single_use_and_platform_bound(api: TestClient, fake: dict) -> None:
    auth = api.post("/api/connections/instagram/authorize").json()["authorization_url"]
    q = parse_qs(urlparse(auth).query)
    assert q["scope"] == ["instagram_business_basic"] and q["response_type"] == ["code"]
    state = q["state"][0]
    # Using an Instagram state on the YouTube callback fails...
    r = api.get(
        "/api/connections/youtube/callback",
        params={"code": "GCODE", "state": state},
        follow_redirects=False,
    )
    assert "error=state" in r.headers["location"]
    # ...and the state was consumed, so it cannot be replayed on Instagram either.
    r = api.get(
        "/api/connections/instagram/callback",
        params={"code": "IGCODE", "state": state},
        follow_redirects=False,
    )
    assert "error=state" in r.headers["location"]
    r = api.get(
        "/api/connections/instagram/callback",
        params={"error": "access_denied"},
        follow_redirects=False,
    )
    assert "error=denied" in r.headers["location"]


def test_instagram_connect_stores_encrypted_token_and_never_exposes_it(
    api: TestClient, fake: dict
) -> None:
    conn_id = connect(api, "instagram", "IGCODE#_")  # Instagram appends "#_"
    body = api.get("/api/connections").json()
    conn = body["instagram"]["connections"][0]
    assert conn["display_name"] == "@creator_demo"
    assert "token" not in " ".join(conn.keys()).replace("token_expires_at", "")
    assert fake_platforms.IG_LONG_TOKEN not in str(body)
    with get_sessionmaker()() as db:
        row = db.get(PlatformConnection, uuid.UUID(conn_id))
        assert row is not None and fake_platforms.IG_LONG_TOKEN not in row.access_token_enc
        assert row.token_expires_at is not None
    items = api.get(f"/api/connections/{conn_id}/media").json()["items"]
    assert [i["expected_mode"] for i in items] == ["full_video", "caption_thumbnail", "full_video"]


@pytest.mark.slow
def test_instagram_import_full_video(api: TestClient, fake: dict) -> None:
    conn_id = connect(api, "instagram", "IGCODE")
    r = import_(api, conn_id, url="https://www.instagram.com/reel/DEMOreel001/?igsh=abc")
    assert r.status_code == 202, r.text
    a = api.get(f"/api/analyses/{r.json()['id']}").json()
    assert a["status"] == "completed", a["error_message"]
    assert (a["source"], a["analysis_mode"], a["platform"]) == (
        "instagram",
        "full_video",
        "instagram_reels",
    )
    assert a["duration_seconds"] == pytest.approx(27, abs=0.2)
    assert a["hashtags"] == ["fitness", "protein"]
    assert a["extraction"]["transcript"]["segments"]
    assert api.get(f"/api/analyses/{a['id']}/video").status_code == 200


@pytest.mark.slow
def test_instagram_withheld_file_falls_back_to_caption_and_thumbnail(
    api: TestClient, fake: dict
) -> None:
    conn_id = connect(api, "instagram", "IGCODE")
    r = import_(api, conn_id, media_id="18000000000000002", language="en")
    a = api.get(f"/api/analyses/{r.json()['id']}").json()
    assert a["status"] == "completed" and a["analysis_mode"] == "caption_thumbnail"
    assert a["extraction"]["frames"][0]["reason"] == "thumbnail"
    assert any("Instagram did not provide the video file" in lim for lim in a["limitations"])
    titles = [f["title"] for f in a["findings"]]
    assert "Video frames, speech and audio were not analysed" in titles
    # Caption-only evidence carries no fake timestamps.
    promo = next(
        f
        for f in a["findings"]
        if f["category"] == "disclosure" and f["finding_type"] != "cannot_check"
    )
    assert promo["start_seconds"] is None


def test_instagram_ownership_and_type_checks(api: TestClient, fake: dict) -> None:
    conn_id = connect(api, "instagram", "IGCODE")
    r = import_(api, conn_id, url="https://www.instagram.com/reel/SOMEONEELSE1/")
    assert r.status_code == 403 and "Only your own posts" in r.json()["detail"]
    assert (
        import_(api, conn_id, url="https://www.youtube.com/shorts/dQw4w9WgXcQ").status_code == 400
    )
    assert import_(api, conn_id, media_id="18000000000000003").status_code == 422  # image post
    assert import_(api, conn_id).status_code == 422


def test_redirect_to_unlisted_host_is_blocked(api: TestClient, fake: dict) -> None:
    conn_id = connect(api, "instagram", "IGCODE")
    r = import_(api, conn_id, media_id="18000000000000004")
    a = api.get(f"/api/analyses/{r.json()['id']}").json()
    assert a["status"] == "failed" and "unexpected host" in a["error_message"]


def test_import_can_wait_for_the_owner_file(api: TestClient, fake: dict) -> None:
    conn_id = connect(api, "youtube", "GCODE")
    r = api.post(
        "/api/analyses/import",
        json={
            "connection_id": conn_id,
            "url": "https://youtube.com/shorts/vidOwn00001",
            "language": "en",
            "attach_owner_file": True,
            "client_label": "  Client A  ",
        },
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "awaiting_file"
    stored = api.get(f"/api/analyses/{body['id']}").json()
    assert stored["status"] == "awaiting_file"
    assert stored["analysis_mode"] == "metadata_only"
    assert stored["extraction"] is None
    assert stored["owner_supplied_media"] is False
    assert stored["client_label"] == "Client A"


def test_owner_file_rejects_a_plain_upload(api: TestClient, sample_promo_en: Path) -> None:
    with get_sessionmaker()() as db:
        row = Analysis(
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            platform="youtube_shorts",
            language="en",
            file_ext=".mp4",
            content_type="video/mp4",
            size_bytes=1,
            source="upload",
            status="completed",
            stage="completed",
            progress=100,
        )
        db.add(row)
        db.commit()
        analysis_id = row.id
    with sample_promo_en.open("rb") as fh:
        res = api.post(
            f"/api/analyses/{analysis_id}/owner-file",
            files={"file": ("clip.mp4", fh, "video/mp4")},
        )
    assert res.status_code == 409
    assert "imported post" in res.json()["detail"]


@pytest.mark.slow
def test_owner_file_cross_checks_youtube_without_downloading(
    api: TestClient, fake: dict, sample_promo_en: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn_id = connect(api, "youtube", "GCODE")
    created = api.post(
        "/api/analyses/import",
        json={
            "connection_id": conn_id,
            "url": "https://youtube.com/shorts/vidOwn00001",
            "language": "en",
            "attach_owner_file": True,
        },
    )
    assert created.status_code == 202, created.text
    analysis_id = created.json()["id"]

    def refuse_download(*_args: object, **_kwargs: object) -> int:
        raise AssertionError("platform audiovisual content must not be downloaded")

    monkeypatch.setattr("app.integrations.importer.download", refuse_download)
    with sample_promo_en.open("rb") as fh:
        attached = api.post(
            f"/api/analyses/{analysis_id}/owner-file",
            files={"file": ("sample_promo_en.mp4", fh, "video/mp4")},
        )
    assert attached.status_code == 202, attached.text
    body = api.get(f"/api/analyses/{analysis_id}").json()
    assert body["status"] == "completed", body["error_message"]
    assert body["analysis_mode"] == "cross_checked"
    assert body["owner_supplied_media"] is True
    assert body["extraction"]["frames"]
    assert body["extraction"]["transcript"]["segments"]
    check = body["extraction"]["cross_check"]
    assert check["duration_status"] in {"match", "trimmed", "mismatch"}
    assert check["platform_withheld_media"] is False
    assert any(line["label"] == "Copyright match" for line in check["lines"])
    titles = [f["title"] for f in body["findings"]]
    assert "Video frames, speech and audio were not analysed" not in titles
    assert "Platform copyright matching (Content ID, Rights Manager) was not performed" in titles
    html = api.get(f"/api/analyses/{analysis_id}/report.html").text
    assert "Cross-check" in html
    assert api.get(f"/api/analyses/{analysis_id}/video").status_code == 200


def test_youtube_connect_uses_pkce_and_least_privilege(api: TestClient, fake: dict) -> None:
    auth = api.post("/api/connections/youtube/authorize").json()["authorization_url"]
    q = parse_qs(urlparse(auth).query)
    assert q["code_challenge_method"] == ["S256"] and len(q["code_challenge"][0]) >= 43
    assert q["scope"] == ["https://www.googleapis.com/auth/youtube.readonly"]
    assert q["access_type"] == ["offline"]


@pytest.mark.slow
def test_youtube_metadata_import_ownership_retention_and_disconnect(
    api: TestClient, fake: dict
) -> None:
    conn_id = connect(api, "youtube", "GCODE")
    media = api.get(f"/api/connections/{conn_id}/media").json()["items"]
    assert media[0]["id"] == "vidOwn00001" and media[0]["privacy"] == "private"

    other = import_(api, conn_id, url="https://youtu.be/vidOther001")
    assert other.status_code == 403 and "does not belong" in other.json()["detail"]

    r = import_(api, conn_id, url="https://youtube.com/shorts/vidOwn00001", language="en")
    assert r.status_code == 202, r.text
    a = api.get(f"/api/analyses/{r.json()['id']}").json()
    assert a["status"] == "completed" and a["analysis_mode"] == "metadata_only"
    assert a["source_title"].startswith("My morning routine")
    assert a["hashtags"] == ["shorts", "fitness", "protein"]
    assert a["extraction"]["frames"] == [] and a["extraction"]["transcript"]["segments"] == []
    assert any("captions permission" in lim for lim in a["limitations"])
    html = api.get(f"/api/analyses/{a['id']}/report.html").text
    assert "METADATA REVIEW ONLY" in html and "YouTube import" in html
    cats = {f["category"] for f in a["findings"] if f["finding_type"] != "cannot_check"}
    assert {"disclosure", "spam_deception"} <= cats
    expires = datetime.fromisoformat(a["expires_at"])
    assert expires - datetime.now(UTC) <= timedelta(
        hours=get_settings().youtube_max_retention_hours
    )

    # Disconnect revokes the Google token and deletes imported analyses.
    out = api.delete(f"/api/connections/{conn_id}").json()
    assert out["deleted_analyses"] == 1
    assert fake["revoked"] == [fake_platforms.YT_REFRESH]
    assert api.get(f"/api/analyses/{a['id']}").status_code == 404


@pytest.mark.slow
def test_youtube_captions_when_scope_enabled(
    api: TestClient, fake: dict, monkeypatch: pytest.MonkeyPatch, settings_override: None
) -> None:
    monkeypatch.setenv("YOUTUBE_CAPTIONS_SCOPE", "true")
    get_settings.cache_clear()
    conn_id = connect(api, "youtube", "GCODE")
    assert api.get("/api/connections").json()["youtube"]["connections"][0]["captions_enabled"]
    r = import_(api, conn_id, media_id="vidOwn00001")
    a = api.get(f"/api/analyses/{r.json()['id']}").json()
    segs = a["extraction"]["transcript"]["segments"]
    assert a["extraction"]["transcript"]["provider"] == "youtube_captions"  # human track chosen
    assert [s["id"] for s in segs] == ["T1", "T2", "T3"] and segs[1]["start"] == 7.2
    assert "cured my back pain" in segs[1]["text"]
    timed = [f for f in a["findings"] if f["start_seconds"] is not None]
    assert timed and all(0 <= f["start_seconds"] <= 27 for f in timed)


def test_youtube_token_refresh(api: TestClient, fake: dict) -> None:
    conn_id = connect(api, "youtube", "GCODE")
    with get_sessionmaker()() as db:
        row = db.get(PlatformConnection, uuid.UUID(conn_id))
        assert row is not None
        row.token_expires_at = datetime.now(UTC) - timedelta(minutes=5)
        db.commit()
    assert api.get(f"/api/connections/{conn_id}/media").status_code == 200
    assert fake["token_requests"][-1] == "refresh_token"


def test_connected_accounts_require_encryption_key(
    api: TestClient, monkeypatch: pytest.MonkeyPatch, settings_override: None
) -> None:
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(IntegrationError, match="TOKEN_ENCRYPTION_KEY"):
        common.encrypt_token("x")


def test_unconfigured_platform_returns_503(
    api: TestClient, monkeypatch: pytest.MonkeyPatch, settings_override: None
) -> None:
    monkeypatch.setenv("INSTAGRAM_APP_ID", "")
    get_settings.cache_clear()
    r = api.post("/api/connections/instagram/authorize")
    assert r.status_code == 503 and "not configured" in r.json()["detail"]


def test_no_imported_rows_leak_between_tests() -> None:
    with get_sessionmaker()() as db:
        assert db.scalars(select(Analysis)).all() == []
