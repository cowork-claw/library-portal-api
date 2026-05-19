from fastapi import FastAPI
from fastapi.testclient import TestClient

from app_v2.middleware.auth import APIKeyMiddleware


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(APIKeyMiddleware, api_key="secret", environment="production")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/health/data")
    def health_data():
        return {"status": "ok"}

    @app.get("/api/secure")
    def secure():
        return {"status": "ok"}

    return app


def test_public_and_protected_paths():
    app = _build_app()
    client = TestClient(app)

    assert client.get("/health").status_code == 200
    assert client.get("/health/data").status_code == 401
    assert client.get("/api/secure").status_code == 401

    headers = {"X-API-Key": "secret"}
    assert client.get("/health/data", headers=headers).status_code == 200
    assert client.get("/api/secure", headers=headers).status_code == 200
    assert client.get("/api/secure", params={"api_key": "secret"}).status_code == 200


def test_openclaw_bot_key_is_accepted(monkeypatch):
    monkeypatch.setenv("LIBRARY_PORTAL_API_KEY", "primary-secret")
    monkeypatch.setenv("LIBRARY_PORTAL_OPENCLAW_BOT_API_KEY", "openclaw-secret")

    app = FastAPI()
    app.add_middleware(APIKeyMiddleware, api_key=None, environment="production")

    @app.get("/api/secure")
    def secure():
        return {"status": "ok"}

    client = TestClient(app)

    assert (
        client.get("/api/secure", headers={"X-API-Key": "primary-secret"}).status_code
        == 200
    )
    assert (
        client.get("/api/secure", headers={"X-API-Key": "openclaw-secret"}).status_code
        == 200
    )
