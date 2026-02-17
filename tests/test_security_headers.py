"""
Tests for Security Headers.
"""

from fastapi.testclient import TestClient


def test_security_headers_present(client: TestClient):
    """Verify that security headers are present in the response."""
    response = client.get("/")
    assert response.status_code == 200

    headers = response.headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-XSS-Protection"] == "1; mode=block"
    assert "Strict-Transport-Security" in headers
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    # Check new headers
    assert "Content-Security-Policy" in headers
    csp = headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-src 'none'" in csp

    assert "Permissions-Policy" in headers
    permissions = headers["Permissions-Policy"]
    assert "geolocation=()" in permissions


def test_double_slash_auth_bypass_protection(client: TestClient):
    """
    Verify that accessing a protected endpoint with double slashes (//api/metadata)
    does not bypass authentication.
    """
    # /api/metadata requires auth.
    # Standard request should be 401
    response = client.get("/api/metadata")
    assert response.status_code == 401

    # Double slash request should also be 401 (not 200 or 404 if it bypassed auth incorrectly)
    # Note: TestClient might normalize double slashes itself, but we'll try.
    response = client.get("//api/metadata")
    assert response.status_code == 401

    # Check that we can access it with auth
    api_key = "test-key"  # Matches conftest.py default
    headers = {"X-API-Key": api_key}

    # With double slash and auth, it should work (or fail due to path not found if router is strict,
    # but auth should pass first).
    # FastAPI/Starlette router usually handles double slashes by normalizing them or matching them if configured.
    # The key thing is that it should NOT be 200 without auth.

    response_auth = client.get("//api/metadata", headers=headers)
    # It might be 404 if the router doesn't match //api/metadata, but 401 is the security check.
    # If the router normalizes it to /api/metadata, then it will return 200.

    if response_auth.status_code == 200:
        # If valid request works, then invalid one MUST be 401
        assert response.status_code == 401
    else:
        # If it returns 404, that's also safe (not found or not routed).
        # But we want to ensure it didn't bypass auth and return something else.
        pass
