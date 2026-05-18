import importlib
from fastapi.testclient import TestClient


def test_metrics_enabled_main_reload_is_idempotent(monkeypatch) -> None:
    """Enabling Prometheus metrics must not make app_v2.main reload unsafe."""
    monkeypatch.setenv("LIBRARY_PORTAL_ENVIRONMENT", "production")
    monkeypatch.setenv("LIBRARY_PORTAL_API_KEY", "test-key")
    monkeypatch.setenv("LIBRARY_PORTAL_METRICS_ENABLED", "true")
    monkeypatch.setenv("LIBRARY_PORTAL_LOG_LEVEL", "ERROR")

    import config.config_v2 as config_module

    importlib.reload(config_module)

    import app_v2.main as main_module

    importlib.reload(main_module)
    importlib.reload(main_module)

    with TestClient(main_module.app) as client:
        client.get("/health")
        unauthenticated = client.get("/metrics")
        authenticated = client.get("/metrics", headers={"X-API-Key": "test-key"})

    assert unauthenticated.status_code == 401
    assert authenticated.status_code == 200
    assert "http_requests_total" in authenticated.text
    assert "http_request_duration_seconds" in authenticated.text

    monkeypatch.setenv("LIBRARY_PORTAL_METRICS_ENABLED", "false")
    importlib.reload(config_module)
    importlib.reload(main_module)
