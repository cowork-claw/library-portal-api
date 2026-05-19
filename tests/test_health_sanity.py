from time import perf_counter
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app_v2.main import app
from app_v2.routes import health


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_check_staging_error_sanitization(client, tmp_path, monkeypatch):
    """Test that health check handles staging file errors gracefully and sanitizes messages."""
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "pending_review.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(health.settings, "STAGING_DIRECTORY", staging_dir)

    with patch(
        "pathlib.Path.read_text",
        side_effect=PermissionError("/secret/path/to/staging.json"),
    ):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()

        # Verify the staging component status
        staging = data["components"]["staging"]
        assert staging["status"] == "degraded"
        # Check that the message contains the exception type but NOT the path
        assert "PermissionError" in staging["message"]
        assert "/secret/path" not in staging["message"]


def test_health_uptime_uses_monotonic_counter(client, monkeypatch):
    monkeypatch.setattr(health, "APP_START_MONOTONIC", perf_counter() - 12.3)

    response = client.get("/health")

    assert response.status_code == 200
    uptime = response.json()["uptime_seconds"]
    assert 12.0 <= uptime <= 13.0


def test_staging_health_rejects_wrong_shaped_papers(tmp_path, monkeypatch):
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "pending_review.json").write_text(
        '{"papers": "not a list"}', encoding="utf-8"
    )
    monkeypatch.setattr(health.settings, "STAGING_DIRECTORY", staging_dir)

    status = health._check_staging_health()

    assert status.status == "degraded"
    assert "ValueError" in status.message
    assert str(staging_dir) not in status.message


def test_staging_health_rejects_non_object_paper_entries(tmp_path, monkeypatch):
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "pending_review.json").write_text(
        '{"papers": ["bad item"]}', encoding="utf-8"
    )
    monkeypatch.setattr(health.settings, "STAGING_DIRECTORY", staging_dir)

    status = health._check_staging_health()

    assert status.status == "degraded"
    assert "ValueError" in status.message
    assert str(staging_dir) not in status.message
