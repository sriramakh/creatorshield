import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.auth import hash_password, install_auth
from app.config import Settings


def client_for(agency, password):
    app = FastAPI()
    settings = Settings(
        _env_file=None,
        app_env="production",
        agency_id=agency,
        pilot_username=agency,
        pilot_password_hash=SecretStr(hash_password(password)),
        frontend_url=f"https://{agency}.example",
    )

    @app.api_route("/api/analyses/private/video", methods=["GET", "DELETE"])
    def video():
        return {"agency": agency}

    install_auth(app, settings)
    return TestClient(app)


def test_every_resource_requires_authentication():
    client = client_for("agency-a", "secret-a")
    for path in [
        "/api/analyses/private/video",
        "/api/rights",
        "/docs",
        "/api/connections/youtube/callback?code=private&state=private",
    ]:
        response = client.get(path)
        assert response.status_code == 401
        assert response.headers["cache-control"] == "no-store"
        assert "Basic" in response.headers["www-authenticate"]


def test_agency_credentials_do_not_cross_deployments():
    a = client_for("agency-a", "secret-a")
    b = client_for("agency-b", "secret-b")
    assert a.get("/api/analyses/private/video", auth=("agency-a", "secret-a")).status_code == 200
    assert b.get("/api/analyses/private/video", auth=("agency-a", "secret-a")).status_code == 401
    assert b.get("/api/analyses/private/video", auth=("agency-b", "secret-b")).json() == {
        "agency": "agency-b"
    }


def test_csrf_and_invalid_credentials():
    client = client_for("agency-a", "secret-a")
    path = "/api/analyses/private/video"
    assert client.get(path, headers={"Authorization": "Basic !!!!"}).status_code == 401
    assert client.get(path, auth=("agency-a", "wrong")).status_code == 401
    for origin in [None, "https://attacker.example", "null"]:
        headers = {"Origin": origin} if origin else {}
        assert (
            client.delete(path, auth=("agency-a", "secret-a"), headers=headers).status_code == 403
        )
    assert (
        client.delete(
            path, auth=("agency-a", "secret-a"), headers={"Origin": "https://agency-a.example"}
        ).status_code
        == 200
    )


def test_production_fails_closed():
    with pytest.raises(RuntimeError):
        install_auth(FastAPI(), Settings(_env_file=None, app_env="production"))


def test_database_binding_refuses_other_agency_and_legacy_data(monkeypatch):
    from unittest.mock import MagicMock

    import app.db
    from app.auth import verify_agency_database

    settings = Settings(_env_file=None, app_env="production", agency_id="agency-a")
    engine = MagicMock()
    conn = engine.begin.return_value.__enter__.return_value
    monkeypatch.setattr(app.db, "get_engine", lambda: engine)
    conn.execute.return_value.scalar.return_value = "agency-b"
    with pytest.raises(RuntimeError, match="different agency"):
        verify_agency_database(settings)
    conn.execute.return_value.scalar.side_effect = [None, True]
    with pytest.raises(RuntimeError, match="fresh database"):
        verify_agency_database(settings)
    conn.execute.return_value.scalar.side_effect = None
    conn.execute.return_value.scalar.return_value = "agency-a"
    verify_agency_database(settings)


def test_auth_cache_expiry_and_isolation(monkeypatch):
    import asyncio

    import app.auth as auth

    calls = []
    now = [100.0]
    monkeypatch.setattr(auth.time, "monotonic", lambda: now[0])

    def check(header, username, stored):
        calls.append(header)
        return header == "good"

    monkeypatch.setattr(auth, "valid_credentials", check)

    async def run():
        verifier = auth.CredentialVerifier("agency-a", "hash")
        assert await verifier.verify("good")
        assert await verifier.verify("good")
        assert len(calls) == 1
        assert "good" not in verifier.cache
        now[0] += 301
        assert await verifier.verify("good")
        assert len(calls) == 2
        assert not await verifier.verify("bad")
        assert not await verifier.verify("bad")
        assert len(calls) == 4
        other = auth.CredentialVerifier("agency-b", "other")
        assert not other.cache

    asyncio.run(run())


def test_password_hash_runs_off_event_loop_and_attempts_are_bounded(monkeypatch):
    import asyncio
    import threading

    import app.auth as auth

    main_thread = threading.get_ident()

    def check(*args):
        assert threading.get_ident() != main_thread
        return False

    monkeypatch.setattr(auth, "valid_credentials", check)

    async def run():
        verifier = auth.CredentialVerifier("agency", "hash")
        for i in range(20):
            assert not await verifier.verify(str(i))
        with pytest.raises(auth.AuthBusy):
            await verifier.verify("another")

    asyncio.run(run())


def test_agency_binding_is_registered_in_metadata():
    from app.db import Base
    from app.models import AgencyBinding

    assert Base.metadata.tables["agency_binding"] is AgencyBinding.__table__
    assert {c.name for c in AgencyBinding.__table__.columns} == {"id", "agency_id"}


def test_hash_concurrency_is_bounded_and_cached_login_survives_limit(monkeypatch):
    import asyncio
    import threading

    import app.auth as auth

    release = threading.Event()

    def check(header, *args):
        if header == "good":
            return True
        assert release.wait(timeout=5)
        return False

    monkeypatch.setattr(auth, "valid_credentials", check)

    async def run():
        verifier = auth.CredentialVerifier("agency", "hash")
        assert await verifier.verify("good")
        pending = [asyncio.create_task(verifier.verify(str(i))) for i in range(2)]
        try:
            # Each task acquires a slot before yielding to its worker thread.
            await asyncio.sleep(0)
            with pytest.raises(auth.AuthBusy):
                await verifier.verify("third")
            assert await verifier.verify("good")
        finally:
            release.set()
            assert await asyncio.gather(*pending) == [False, False]

    asyncio.run(run())


def test_parallel_requests_with_a_new_login_share_one_hash(monkeypatch):
    import asyncio

    import app.auth as auth

    calls = []

    def check(header, *args):
        calls.append(header)
        return header == "good"

    monkeypatch.setattr(auth, "valid_credentials", check)

    async def run():
        verifier = auth.CredentialVerifier("agency", "hash")
        # A page load after the cache entry lapsed: assets and API calls arrive together.
        assert await asyncio.gather(*(verifier.verify("good") for _ in range(12))) == [True] * 12
        assert await asyncio.gather(*(verifier.verify("bad") for _ in range(12))) == [False] * 12
        assert calls == ["good", "bad"]

    asyncio.run(run())


def test_active_session_keeps_its_cache_entry(monkeypatch):
    import asyncio

    import app.auth as auth

    calls = []
    now = [100.0]
    monkeypatch.setattr(auth.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(auth, "valid_credentials", lambda header, *a: calls.append(header) or True)

    async def run():
        verifier = auth.CredentialVerifier("agency", "hash")
        for _ in range(5):
            assert await verifier.verify("good")
            now[0] += 200  # used every 200 s for 1000 s
        assert len(calls) == 1
        now[0] += 301  # idle longer than the timeout
        assert await verifier.verify("good")
        assert len(calls) == 2

    asyncio.run(run())
