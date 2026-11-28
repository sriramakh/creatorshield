"""The real application with the pilot login enabled (no database needed).

Every route of create_app() must refuse anonymous requests, cross-site writes must be
refused, and request bodies must be capped while they arrive.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.config import get_settings

ORIGIN = "https://agency-a.example"
AUTH = ("agency-a", "correct horse battery staple")
_HASH = hash_password(AUTH[1])


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AGENCY_ID", "agency-a")
    monkeypatch.setenv("PILOT_USERNAME", AUTH[0])
    monkeypatch.setenv("PILOT_PASSWORD_HASH", _HASH)
    monkeypatch.setenv("FRONTEND_URL", ORIGIN)
    monkeypatch.setenv("MAX_UPLOAD_MB", "3")
    monkeypatch.setenv("RIGHTS_PROOF_MAX_MB", "1")
    monkeypatch.setenv("MAINTENANCE_INTERVAL_SECONDS", "0")
    get_settings.cache_clear()
    from app.main import create_app

    # No lifespan (no `with`): nothing here touches the database.
    yield TestClient(create_app())
    get_settings.cache_clear()


AID = uuid.uuid4()
PROTECTED_GETS = [
    f"/api/analyses/{AID}/video",
    f"/api/analyses/{AID}/frames/F1.jpg",
    f"/api/analyses/{AID}/report.html",
    f"/api/analyses/{AID}/report.html?download=true",
    f"/api/analyses/{AID}/report.json",
    f"/api/analyses/{AID}/evidence-pack.zip",
    f"/api/rights/{AID}/proof",
    f"/api/analyses/{AID}",
    "/api/analyses",
    "/api/rights",
    "/api/catalogue",
    "/api/connections",
    f"/api/connections/{AID}/media",
    "/api/connections/youtube/callback?code=private&state=private",
    "/api/connections/instagram/callback?code=private&state=private",
    "/api/health",
    "/api/config",
    "/api/policies",
    "/api/provenance/status",
    "/auth/verify",
    "/docs",
    "/openapi.json",
]


@pytest.mark.parametrize("path", PROTECTED_GETS)
def test_every_download_and_page_requires_login(client: TestClient, path: str) -> None:
    for creds in (None, ("agency-a", "wrong"), ("someone-else", AUTH[1])):
        r = client.get(path, auth=creds)
        assert r.status_code == 401, (path, creds, r.status_code)
        assert "Basic" in r.headers["www-authenticate"]
        assert r.headers["cache-control"] == "no-store"
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/analyses"),
        ("POST", f"/api/analyses/{AID}/rerun"),
        ("POST", f"/api/analyses/{AID}/owner-file"),
        ("DELETE", f"/api/analyses/{AID}"),
        ("POST", "/api/analyses/import"),
        ("POST", "/api/connections/youtube/authorize"),
        ("DELETE", f"/api/connections/{AID}"),
        ("POST", "/api/rights"),
        ("DELETE", f"/api/rights/{AID}"),
        ("POST", "/api/catalogue"),
        ("POST", f"/api/analyses/{AID}/lookups/web"),
        ("HEAD", f"/api/analyses/{AID}/video"),
        ("OPTIONS", "/api/analyses"),
    ],
)
def test_writes_head_and_options_require_login(client: TestClient, method: str, path: str) -> None:
    r = client.request(method, path, headers={"Origin": ORIGIN})
    assert r.status_code == 401


def test_auth_verify_for_the_gateway(client: TestClient) -> None:
    r = client.get("/auth/verify", auth=AUTH)
    assert r.status_code == 200 and r.json() == {"agency_id": "agency-a"}
    assert r.headers["cache-control"] == "no-store"


def test_liveness_is_public_but_reveals_nothing(client: TestClient) -> None:
    r = client.get("/api/health/live")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_origin_and_referer_checks_on_writes(client: TestClient) -> None:
    # Unknown platform -> 404 from the route itself once the origin check passes.
    path = "/api/connections/nope/authorize"
    assert client.post(path, auth=AUTH).status_code == 403
    assert (
        client.post(path, auth=AUTH, headers={"Origin": "https://evil.example"}).status_code == 403
    )
    assert client.post(path, auth=AUTH, headers={"Origin": "null"}).status_code == 403
    assert client.post(path, auth=AUTH, headers={"Origin": ORIGIN}).status_code == 404
    assert (
        client.post(path, auth=AUTH, headers={"Referer": f"{ORIGIN}/analyses/new"}).status_code
        == 404
    )
    assert (
        client.post(path, auth=AUTH, headers={"Referer": "https://evil.example/x"}).status_code
        == 403
    )
    # A matching Referer never overrides a foreign Origin.
    assert (
        client.post(
            path, auth=AUTH, headers={"Origin": "https://evil.example", "Referer": ORIGIN + "/"}
        ).status_code
        == 403
    )
    # Safe methods are not origin-checked (they must not change state).
    assert client.head("/api/config", auth=AUTH).status_code != 403
    assert client.options("/api/config", auth=AUTH).status_code != 403


def _multipart(size: int, boundary: str = "csboundary") -> tuple[bytes, str]:
    head = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="platform"\r\n\r\nyoutube_shorts\r\n'
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="language"\r\n\r\nen\r\n'
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="clip.mp4"\r\n'
        "Content-Type: video/mp4\r\n\r\n"
    ).encode()
    tail = f"\r\n--{boundary}--\r\n".encode()
    return head + b"\x00" * size + tail, f"multipart/form-data; boundary={boundary}"


@pytest.fixture
def no_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    """The handlers must never run for an oversized body."""

    def refuse(*_a: object, **_k: object) -> None:
        raise AssertionError("upload handler reached storage")

    monkeypatch.setattr("app.api.routes.get_storage", refuse)
    monkeypatch.setattr("app.api.provenance.get_storage", refuse)


@pytest.mark.parametrize(
    "path", ["/api/analyses", f"/api/analyses/{AID}/owner-file", "/api/catalogue"]
)
def test_declared_oversized_body_is_refused_up_front(
    client: TestClient, no_storage: None, path: str
) -> None:
    body, ctype = _multipart(5 * 1024 * 1024)
    r = client.post(
        path, content=body, auth=AUTH, headers={"Origin": ORIGIN, "Content-Type": ctype}
    )
    assert r.status_code == 413
    assert "too large" in r.json()["detail"].lower()


def test_streamed_oversized_body_is_cut_off_while_arriving(
    client: TestClient, no_storage: None
) -> None:
    body, ctype = _multipart(5 * 1024 * 1024)
    sent = []

    def chunks() -> Iterator[bytes]:
        for i in range(0, len(body), 64 * 1024):
            sent.append(i)
            yield body[i : i + 64 * 1024]

    # No Content-Length (chunked): the middleware counts bytes as they arrive.
    r = client.post(
        "/api/analyses",
        content=chunks(),
        auth=AUTH,
        headers={"Origin": ORIGIN, "Content-Type": ctype},
    )
    assert r.status_code == 413


def test_rights_proof_has_its_own_smaller_cap(client: TestClient, no_storage: None) -> None:
    # 2.5 MB: under the video cap (3 MB + slack), over the proof cap (1 MB + slack).
    body, ctype = _multipart(int(2.5 * 1024 * 1024))
    r = client.post(
        "/api/rights", content=body, auth=AUTH, headers={"Origin": ORIGIN, "Content-Type": ctype}
    )
    assert r.status_code == 413


def test_body_under_the_cap_reaches_the_handler(client: TestClient) -> None:
    body, ctype = _multipart(1024)
    body = body.replace(b"youtube_shorts", b"tiktok")
    r = client.post(
        "/api/analyses", content=body, auth=AUTH, headers={"Origin": ORIGIN, "Content-Type": ctype}
    )
    assert r.status_code == 422 and "platform" in r.json()["detail"]


def test_negative_list_limits_are_rejected(client: TestClient) -> None:
    for query in ("limit=-1", "limit=0", "limit=201", "offset=-1"):
        assert client.get(f"/api/analyses?{query}", auth=AUTH).status_code == 422
