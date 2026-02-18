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

    # Check new headers for normal endpoints (strict CSP)
    assert "Content-Security-Policy" in headers
    csp = headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-src 'none'" in csp

    assert "Permissions-Policy" in headers
    permissions = headers["Permissions-Policy"]
    assert "geolocation=()" in permissions
    assert "xr-spatial-tracking=()" in permissions


def test_docs_csp_relaxed(client: TestClient):
    """Verify that documentation endpoints have a relaxed CSP."""
    # Docs endpoint should allow unsafe-inline and CDN
    response = client.get("/docs")
    assert response.status_code == 200

    headers = response.headers
    assert "Content-Security-Policy" in headers
    csp = headers["Content-Security-Policy"]

    # Should allow scripts and styles from self and CDN, and inline
    assert "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net" in csp
    assert "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net" in csp


def test_double_slash_auth_bypass_protection(
    client: TestClient, api_key_headers: dict
):
    """
    Verify that accessing a protected endpoint with double slashes (//api/metadata)
    does not bypass authentication.
    """
    # Use absolute URL to prevent TestClient/httpx from normalizing the path automatically
    base_url = str(client.base_url)

    # 1. Standard request should be 401 Unauthorized
    response = client.get("/api/metadata")
    assert response.status_code == 401

    # 2. Double slash request should also be 401 (not 200 or 404 if it bypassed auth incorrectly)
    # Using absolute URL to ensure double slash is sent
    double_slash_url = f"{base_url}//api/metadata"
    response_double = client.get(double_slash_url)
    assert response_double.status_code == 401

    # 3. With valid auth, request should not be rejected by auth middleware.
    response_auth = client.get(double_slash_url, headers=api_key_headers)
    assert response_auth.status_code in (200, 404, 307), (
        "Expected authenticated double-slash request to be routed/redirected "
        f"(200/404/307), got {response_auth.status_code}"
    )
