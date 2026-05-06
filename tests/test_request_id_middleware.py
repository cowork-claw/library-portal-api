"""
Tests for RequestIDMiddleware.

Validates:
- Requests without X-Request-ID get a generated UUID in response headers
- Requests with X-Request-ID echo the exact same value back
- Generated request IDs are non-empty and valid UUID4 format
- 401 responses include X-Request-ID header
- 403 responses include X-Request-ID header
- Middleware is registered outermost in the stack
- Request ID appears on public and protected endpoints
"""

import re
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app_v2.middleware.auth import APIKeyMiddleware
from app_v2.middleware.request_id import RequestIDMiddleware
from app_v2.middleware.security import SecurityHeadersMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I
)

API_KEY = "test-key"


def _build_app() -> FastAPI:
    """Build a minimal FastAPI app with the correct middleware stack order."""
    app = FastAPI()

    # Middleware is registered in reverse order (last registered = outermost).
    # Desired outermost → innermost: RequestID → SecurityHeaders → APIKey
    # So register innermost first.
    app.add_middleware(APIKeyMiddleware, api_key=API_KEY, environment="production")
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/")
    def root():
        return {"status": "ok"}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/secure")
    def secure():
        return {"status": "ok"}

    return app


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestRequestIDGenerated:
    """VAL-SEC-009: Request ID is generated when not provided by client."""

    def test_generated_request_id_present_in_response(self):
        """Requests without X-Request-ID get a generated UUID in response headers."""
        app = _build_app()
        client = TestClient(app)

        response = client.get("/")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers

        request_id = response.headers["X-Request-ID"]
        assert request_id  # non-empty
        assert UUID4_RE.match(request_id), f"Not a valid UUID4: {request_id}"

    def test_generated_request_id_is_uuid4(self):
        """Generated request IDs are valid UUID4 format."""
        app = _build_app()
        client = TestClient(app)

        response = client.get("/")
        request_id = response.headers["X-Request-ID"]
        # Validate it's a parseable UUID v4
        parsed = uuid.UUID(request_id)
        assert parsed.version == 4

    def test_each_request_gets_unique_id(self):
        """Each request gets a unique request ID."""
        app = _build_app()
        client = TestClient(app)

        ids = set()
        for _ in range(10):
            response = client.get("/")
            ids.add(response.headers["X-Request-ID"])

        assert len(ids) == 10, "Request IDs should be unique across requests"


class TestRequestIDPreserved:
    """VAL-SEC-010: Client-provided request ID is preserved in response."""

    def test_client_request_id_echoed_back(self):
        """Requests with X-Request-ID echo the exact same value back."""
        app = _build_app()
        client = TestClient(app)

        custom_id = "custom-id-12345"
        response = client.get("/", headers={"X-Request-ID": custom_id})
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == custom_id

    def test_client_uuid_preserved(self):
        """A client-provided UUID is echoed back exactly."""
        app = _build_app()
        client = TestClient(app)

        client_uuid = str(uuid.uuid4())
        response = client.get("/", headers={"X-Request-ID": client_uuid})
        assert response.headers["X-Request-ID"] == client_uuid

    def test_empty_request_id_replaced(self):
        """An empty X-Request-ID header is treated as absent and replaced."""
        app = _build_app()
        client = TestClient(app)

        response = client.get("/", headers={"X-Request-ID": ""})
        # The middleware should generate a new ID when the header is empty
        request_id = response.headers["X-Request-ID"]
        assert request_id  # non-empty, i.e., a generated UUID
        assert UUID4_RE.match(request_id)


class TestRequestIDOnAuthErrors:
    """Error responses must still include X-Request-ID."""

    def test_401_includes_request_id(self):
        """401 responses include X-Request-ID header."""
        app = _build_app()
        client = TestClient(app)

        response = client.get("/api/secure")  # no API key → 401
        assert response.status_code == 401
        assert "X-Request-ID" in response.headers

        request_id = response.headers["X-Request-ID"]
        assert request_id
        assert UUID4_RE.match(request_id)

    def test_403_includes_request_id(self):
        """403 responses include X-Request-ID header."""
        app = _build_app()
        client = TestClient(app)

        response = client.get("/api/secure", headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 403
        assert "X-Request-ID" in response.headers

        request_id = response.headers["X-Request-ID"]
        assert request_id
        assert UUID4_RE.match(request_id)

    def test_401_with_client_request_id_echoed(self):
        """401 responses echo back the client-provided request ID."""
        app = _build_app()
        client = TestClient(app)

        custom_id = "trace-abc-123"
        response = client.get(
            "/api/secure",
            headers={"X-Request-ID": custom_id},
        )
        assert response.status_code == 401
        assert response.headers["X-Request-ID"] == custom_id

    def test_403_with_client_request_id_echoed(self):
        """403 responses echo back the client-provided request ID."""
        app = _build_app()
        client = TestClient(app)

        custom_id = "trace-def-456"
        response = client.get(
            "/api/secure",
            headers={"X-API-Key": "wrong", "X-Request-ID": custom_id},
        )
        assert response.status_code == 403
        assert response.headers["X-Request-ID"] == custom_id


class TestRequestIDMiddlewareOrdering:
    """VAL-CROSS-012: Middleware ordering ensures headers on auth failures."""

    def test_request_id_and_security_headers_on_401(self):
        """401 response has both X-Request-ID and all security headers."""
        app = _build_app()
        client = TestClient(app)

        response = client.get("/api/secure")
        assert response.status_code == 401

        # Request ID
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"]

        # Security headers (subset check)
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert "Content-Security-Policy" in response.headers

    def test_request_id_and_security_headers_on_403(self):
        """403 response has both X-Request-ID and all security headers."""
        app = _build_app()
        client = TestClient(app)

        response = client.get("/api/secure", headers={"X-API-Key": "bad"})
        assert response.status_code == 403

        assert "X-Request-ID" in response.headers
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_request_id_on_protected_success(self):
        """Authenticated requests include X-Request-ID on success."""
        app = _build_app()
        client = TestClient(app)

        response = client.get(
            "/api/secure",
            headers={"X-API-Key": API_KEY},
        )
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers

    def test_request_id_on_public_endpoints(self):
        """Public endpoints also get request IDs."""
        app = _build_app()
        client = TestClient(app)

        for path in ["/", "/health"]:
            response = client.get(path)
            assert response.status_code == 200
            assert "X-Request-ID" in response.headers
            assert UUID4_RE.match(response.headers["X-Request-ID"])


class TestRequestIDWithFullApp:
    """Integration tests using the real app client fixture."""

    def test_request_id_on_api_endpoint(
        self, client: TestClient, api_key_headers: dict
    ):
        """Real app: /api/papers returns X-Request-ID."""
        response = client.get("/api/papers", headers=api_key_headers)
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers

    def test_request_id_on_401_real_app(self, client: TestClient):
        """Real app: 401 on /api/papers without key includes X-Request-ID."""
        response = client.get("/api/papers")
        assert response.status_code == 401
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"]

    def test_custom_request_id_echoed_real_app(
        self, client: TestClient, api_key_headers: dict
    ):
        """Real app: custom X-Request-ID is echoed back."""
        headers = {**api_key_headers, "X-Request-ID": "my-trace-id-999"}
        response = client.get("/api/papers", headers=headers)
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "my-trace-id-999"

    def test_request_id_on_lookup_404(self, client: TestClient, api_key_headers: dict):
        """Real app: 404 from lookup includes X-Request-ID."""
        headers = {**api_key_headers, "X-Request-ID": "lookup-trace"}
        response = client.get(
            "/api/papers/lookup?url=https://example.com/nonexistent.pdf",
            headers=headers,
        )
        assert response.status_code == 404
        assert response.headers["X-Request-ID"] == "lookup-trace"
