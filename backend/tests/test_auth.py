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
