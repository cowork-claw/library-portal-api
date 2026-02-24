from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app_v2.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_check_staging_error_sanitization(client):
    """Test that health check handles staging file errors gracefully and sanitizes messages."""

    # Mock open to raise an exception
    with patch("builtins.open", side_effect=PermissionError("/secret/path/to/staging.json")):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()

        # Verify the staging component status
        staging = data["components"]["staging"]
        assert staging["status"] == "degraded"
        # Check that the message contains the exception type but NOT the path
        assert "PermissionError" in staging["message"]
        assert "/secret/path" not in staging["message"]
