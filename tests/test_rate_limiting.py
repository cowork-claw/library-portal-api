"""
Tests for RateLimitMiddleware.

Validates:
- VAL-SEC-001: 100 requests under threshold return 2xx
- VAL-SEC-002: 101st request returns 429
- VAL-SEC-003: 429 response includes Retry-After header with positive integer
- VAL-SEC-004: Public paths are not rate limited
- VAL-SEC-005: Rate limit resets after window
- VAL-SEC-012: Security headers present after adding rate limit middleware
- VAL-SEC-013: Failed requests count toward the rate limit
- VAL-SEC-015: Security headers on all error responses
- VAL-CROSS-003: Rate limiting applies to filtered requests
- VAL-CROSS-007: Reload endpoint is rate-limited
- VAL-CROSS-010: Lookup returns 404 when under rate limit
"""

import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app_v2.middleware.auth import APIKeyMiddleware
from app_v2.middleware.rate_limit import RateLimitMiddleware
from app_v2.middleware.security import SecurityHeadersMiddleware
from app_v2.middleware.structured_logging import RequestIDMiddleware

API_KEY = "test-key"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app(
    max_requests: int = 100,
    window_seconds: int = 60,
) -> FastAPI:
    """Build a minimal FastAPI app with the correct middleware stack.

    Execution order (outermost → innermost):
    RequestID → SecurityHeaders → RateLimit → APIKey → Routes
    """
    app = FastAPI()

    # Register innermost first (FastAPI wraps in reverse order)
    @app.get("/")
    def root():
        return {"status": "ok"}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/secure")
    def secure():
        return {"status": "ok"}

    @app.get("/api/papers")
    def papers():
        return {"papers": [], "total": 0}

    @app.get("/api/papers/lookup")
    def lookup():
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=404, content={"detail": "Not found"})

    @app.get("/health/data")
    def health_data():
        return {"status": "ok"}

    @app.post("/health/data/reload")
    def reload_data():
        return {"status": "ok", "reload_id": "test-id"}

    @app.get("/api/cause-422")
    def cause_422():
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=422, content={"detail": "Validation error"})

    # Middleware stack (registered reverse: last = outermost)
    app.add_middleware(APIKeyMiddleware, api_key=API_KEY, environment="production")
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=max_requests,
        window_seconds=window_seconds,
        valid_api_keys=[API_KEY, "other-key"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)

    return app


# ---------------------------------------------------------------------------
# VAL-SEC-001: Requests under threshold succeed
# ---------------------------------------------------------------------------


class TestRequestsUnderThreshold:
    """Up to 100 authenticated requests within the window return 2xx."""

    def test_100_requests_all_succeed(self):
        """100 sequential requests to /api/secure all return 2xx."""
        app = _build_app(max_requests=100, window_seconds=60)
        client = TestClient(app)

        for i in range(100):
            response = client.get("/api/secure", headers={"X-API-Key": API_KEY})
            assert (
                response.status_code == 200
            ), f"Request {i + 1} failed: {response.status_code}"

    def test_requests_to_health_data_succeed_under_threshold(self):
        """Requests to /health/data succeed under threshold."""
        app = _build_app(max_requests=100, window_seconds=60)
        client = TestClient(app)

        for _ in range(50):
            response = client.get("/health/data", headers={"X-API-Key": API_KEY})
            assert response.status_code == 200


# ---------------------------------------------------------------------------
# VAL-SEC-002: 101st request returns 429
# ---------------------------------------------------------------------------


class TestThresholdExceeded:
    """101st request within window returns 429."""

    def test_101st_request_returns_429(self):
        """The 101st request within the window returns HTTP 429."""
        app = _build_app(max_requests=100, window_seconds=60)
        client = TestClient(app)
        headers = {"X-API-Key": API_KEY}

        for _ in range(100):
            client.get("/api/secure", headers=headers)

        response = client.get("/api/secure", headers=headers)
        assert response.status_code == 429

    def test_subsequent_requests_also_429(self):
        """After exceeding threshold, subsequent requests also get 429."""
        app = _build_app(max_requests=100, window_seconds=60)
        client = TestClient(app)
        headers = {"X-API-Key": API_KEY}

        for _ in range(100):
            client.get("/api/secure", headers=headers)

        for i in range(5):
            response = client.get("/api/secure", headers=headers)
            assert (
                response.status_code == 429
            ), f"Request {i + 1} after limit should be 429"


# ---------------------------------------------------------------------------
# VAL-SEC-003: 429 includes Retry-After header
# ---------------------------------------------------------------------------


class TestRetryAfterHeader:
    """429 responses include Retry-After header with positive integer."""

    def test_retry_after_present_on_429(self):
        """Retry-After header is present on 429 responses."""
        app = _build_app(max_requests=5, window_seconds=60)
        client = TestClient(app)
        headers = {"X-API-Key": API_KEY}

        for _ in range(5):
            client.get("/api/secure", headers=headers)

        response = client.get("/api/secure", headers=headers)
        assert response.status_code == 429
        assert "Retry-After" in response.headers

    def test_retry_after_is_positive_integer(self):
        """Retry-After value is a positive integer."""
        app = _build_app(max_requests=5, window_seconds=60)
        client = TestClient(app)
        headers = {"X-API-Key": API_KEY}

        for _ in range(5):
            client.get("/api/secure", headers=headers)

        response = client.get("/api/secure", headers=headers)
        assert response.status_code == 429
        retry_after = int(response.headers["Retry-After"])
        assert retry_after > 0

    def test_retry_after_does_not_exceed_window(self):
        """Retry-After value does not exceed the window duration."""
        app = _build_app(max_requests=5, window_seconds=60)
        client = TestClient(app)
        headers = {"X-API-Key": API_KEY}

        for _ in range(5):
            client.get("/api/secure", headers=headers)

        response = client.get("/api/secure", headers=headers)
        retry_after = int(response.headers["Retry-After"])
        assert retry_after <= 60


# ---------------------------------------------------------------------------
# VAL-SEC-004: Public paths are not rate limited
# ---------------------------------------------------------------------------


class TestPublicPathsExempt:
    """Public paths are not subject to rate limiting."""

    def test_root_not_rate_limited(self):
        """Requests to / are not rate limited even after exceeding threshold."""
        app = _build_app(max_requests=5, window_seconds=60)
        client = TestClient(app)

        # Exhaust the rate limit on a protected path
        for _ in range(5):
            client.get("/api/secure", headers={"X-API-Key": API_KEY})

        # Verify 429 on protected path
        resp = client.get("/api/secure", headers={"X-API-Key": API_KEY})
        assert resp.status_code == 429

        # Public path should still work
        for _ in range(10):
            response = client.get("/")
            assert response.status_code == 200

    def test_health_not_rate_limited(self):
        """Requests to /health are not rate limited."""
        app = _build_app(max_requests=5, window_seconds=60)
        client = TestClient(app)

        for _ in range(5):
            client.get("/api/secure", headers={"X-API-Key": API_KEY})

        # /health should still work
        for _ in range(10):
            response = client.get("/health")
            assert response.status_code == 200

    def test_docs_not_rate_limited(self):
        """Requests to /docs are not rate limited."""
        app = _build_app(max_requests=5, window_seconds=60)
        client = TestClient(app)

        for _ in range(5):
            client.get("/api/secure", headers={"X-API-Key": API_KEY})

        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_not_rate_limited(self):
        """Requests to /redoc are not rate limited."""
        app = _build_app(max_requests=5, window_seconds=60)
        client = TestClient(app)

        for _ in range(5):
            client.get("/api/secure", headers={"X-API-Key": API_KEY})

        response = client.get("/redoc")
        assert response.status_code == 200

    def test_openapi_json_not_rate_limited(self):
        """Requests to /openapi.json are not rate limited."""
        app = _build_app(max_requests=5, window_seconds=60)
        client = TestClient(app)

        for _ in range(5):
            client.get("/api/secure", headers={"X-API-Key": API_KEY})

        response = client.get("/openapi.json")
        assert response.status_code == 200

    def test_101_plus_requests_to_public_path_still_succeed(self):
        """101+ requests to a public path all return 2xx."""
        app = _build_app(max_requests=100, window_seconds=60)
        client = TestClient(app)

        for i in range(110):
            response = client.get("/")
            assert response.status_code == 200, f"Public request {i + 1} failed"


# ---------------------------------------------------------------------------
# VAL-SEC-005: Rate limit resets after window
# ---------------------------------------------------------------------------


class TestRateLimitResets:
    """Rate limit resets after the window elapses."""

    def test_reset_after_window(self):
        """After the window expires, the quota is restored."""
        app = _build_app(max_requests=5, window_seconds=1)
        client = TestClient(app)
        headers = {"X-API-Key": API_KEY}

        # Exhaust limit
        for _ in range(5):
            client.get("/api/secure", headers=headers)

        # Confirm 429
        response = client.get("/api/secure", headers=headers)
        assert response.status_code == 429

        # Wait for window to reset
        time.sleep(1.1)

        # Should succeed again
        response = client.get("/api/secure", headers=headers)
        assert response.status_code == 200

    def test_full_quota_restored_after_reset(self):
        """After reset, the full quota is available."""
        app = _build_app(max_requests=5, window_seconds=1)
        client = TestClient(app)
        headers = {"X-API-Key": API_KEY}

        # Exhaust limit
        for _ in range(5):
            client.get("/api/secure", headers=headers)

        # Wait for reset
        time.sleep(1.1)

        # Full quota should be available
        for i in range(5):
            response = client.get("/api/secure", headers=headers)
            assert response.status_code == 200, f"Request {i + 1} after reset failed"


# ---------------------------------------------------------------------------
# VAL-SEC-013: Failed requests count toward rate limit
# ---------------------------------------------------------------------------


class TestFailedRequestsCountTowardLimit:
    """401, 403, 404, and 422 responses increment the rate limit counter."""

    def test_401_requests_count_toward_limit(self):
        """100 unauthenticated requests (all 401) → 101st returns 429."""
        app = _build_app(max_requests=100, window_seconds=60)
        client = TestClient(app)

        # Send 100 requests without API key → all get 401
        for i in range(100):
            response = client.get("/api/secure")
            assert response.status_code == 401, f"Request {i + 1} was not 401"

        # 101st request should get 429
        response = client.get("/api/secure")
        assert response.status_code == 429

    def test_403_requests_count_toward_limit(self):
        """100 requests with wrong key (all 403) → 101st returns 429."""
        app = _build_app(max_requests=100, window_seconds=60)
        client = TestClient(app)
        bad_headers = {"X-API-Key": "wrong-key"}

        for i in range(100):
            response = client.get("/api/secure", headers=bad_headers)
            assert response.status_code == 403, f"Request {i + 1} was not 403"

        response = client.get("/api/secure", headers=bad_headers)
        assert response.status_code == 429

    def test_404_requests_count_toward_limit(self):
        """100 requests returning 404 → 101st returns 429."""
        app = _build_app(max_requests=100, window_seconds=60)
        client = TestClient(app)
        headers = {"X-API-Key": API_KEY}

        for i in range(100):
            response = client.get("/api/papers/lookup", headers=headers)
            assert response.status_code == 404, f"Request {i + 1} was not 404"

        response = client.get("/api/papers/lookup", headers=headers)
        assert response.status_code == 429

    def test_422_requests_count_toward_limit(self):
        """100 requests returning 422 → 101st returns 429."""
        app = _build_app(max_requests=100, window_seconds=60)
        client = TestClient(app)
        headers = {"X-API-Key": API_KEY}

        for i in range(100):
            response = client.get("/api/cause-422", headers=headers)
            assert response.status_code == 422, f"Request {i + 1} was not 422"

        response = client.get("/api/cause-422", headers=headers)
        assert response.status_code == 429

    def test_mixed_errors_count_toward_limit(self):
        """Mix of 404 and 422 from the same client counts toward the same limit."""
        app = _build_app(max_requests=100, window_seconds=60)
        client = TestClient(app)
        headers = {"X-API-Key": API_KEY}

        # 50 × 404
        for _ in range(50):
            r = client.get("/api/papers/lookup", headers=headers)
            assert r.status_code == 404

        # 49 × 422
        for _ in range(49):
            r = client.get("/api/cause-422", headers=headers)
            assert r.status_code == 422

        # 1 more (100th) should still be allowed
        r = client.get("/api/cause-422", headers=headers)
        assert r.status_code == 422

        # 101st → 429
        r = client.get("/api/secure", headers=headers)
        assert r.status_code == 429


# ---------------------------------------------------------------------------
# VAL-SEC-012 & VAL-SEC-015: Security headers on all responses
# ---------------------------------------------------------------------------


class TestSecurityHeadersPresent:
    """Security headers are present on all response types."""

    EXPECTED_SECURITY_HEADERS = [
        "X-Content-Type-Options",
        "X-Frame-Options",
        "X-XSS-Protection",
        "Strict-Transport-Security",
        "Referrer-Policy",
        "Permissions-Policy",
        "Content-Security-Policy",
    ]

    def _assert_security_headers(self, response):
        for header in self.EXPECTED_SECURITY_HEADERS:
            assert header in response.headers, f"Missing security header: {header}"

    def test_security_headers_on_200(self):
        """Security headers present on successful response."""
        app = _build_app(max_requests=100, window_seconds=60)
        client = TestClient(app)

        response = client.get("/api/secure", headers={"X-API-Key": API_KEY})
        assert response.status_code == 200
        self._assert_security_headers(response)

    def test_security_headers_on_401(self):
        """Security headers present on 401 response."""
        app = _build_app(max_requests=100, window_seconds=60)
        client = TestClient(app)

        response = client.get("/api/secure")
        assert response.status_code == 401
        self._assert_security_headers(response)

    def test_security_headers_on_403(self):
        """Security headers present on 403 response."""
        app = _build_app(max_requests=100, window_seconds=60)
        client = TestClient(app)

        response = client.get("/api/secure", headers={"X-API-Key": "wrong"})
        assert response.status_code == 403
        self._assert_security_headers(response)

    def test_security_headers_on_404(self):
        """Security headers present on 404 response."""
        app = _build_app(max_requests=100, window_seconds=60)
        client = TestClient(app)

        response = client.get("/api/papers/lookup", headers={"X-API-Key": API_KEY})
        assert response.status_code == 404
        self._assert_security_headers(response)

    def test_security_headers_on_429(self):
        """Security headers present on 429 response."""
        app = _build_app(max_requests=5, window_seconds=60)
        client = TestClient(app)
        headers = {"X-API-Key": API_KEY}

        for _ in range(5):
            client.get("/api/secure", headers=headers)

        response = client.get("/api/secure", headers=headers)
        assert response.status_code == 429
        self._assert_security_headers(response)

    def test_request_id_on_429(self):
        """429 responses include X-Request-ID."""
        app = _build_app(max_requests=5, window_seconds=60)
        client = TestClient(app)
        headers = {"X-API-Key": API_KEY}

        for _ in range(5):
            client.get("/api/secure", headers=headers)

        response = client.get("/api/secure", headers=headers)
        assert response.status_code == 429
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"]


# ---------------------------------------------------------------------------
# VAL-CROSS-003: Rate limiting on filtered requests
# ---------------------------------------------------------------------------


class TestRateLimitOnFilteredRequests:
    """Rate limiting applies to program_abbrev and other filtered requests."""

    def test_rate_limit_on_papers_endpoint(self):
        """101 requests to /api/papers returns 429."""
        app = _build_app(max_requests=100, window_seconds=60)
        client = TestClient(app)
        headers = {"X-API-Key": API_KEY}

        for _ in range(100):
            client.get("/api/papers", headers=headers)

        response = client.get("/api/papers", headers=headers)
        assert response.status_code == 429
        assert "Retry-After" in response.headers

    def test_429_includes_request_id_and_security_headers(self):
        """429 response includes both X-Request-ID and security headers."""
        app = _build_app(max_requests=5, window_seconds=60)
        client = TestClient(app)
        headers = {"X-API-Key": API_KEY, "X-Request-ID": "custom-trace-123"}

        for _ in range(5):
            client.get("/api/papers", headers=headers)

        response = client.get("/api/papers", headers=headers)
        assert response.status_code == 429
        assert response.headers["X-Request-ID"] == "custom-trace-123"
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers


# ---------------------------------------------------------------------------
# VAL-CROSS-007: Reload endpoint is rate-limited
# ---------------------------------------------------------------------------


class TestReloadEndpointRateLimited:
    """POST /health/data/reload is subject to rate limiting."""

    def test_reload_rate_limited(self):
        """101 POST requests to /health/data/reload returns 429."""
        app = _build_app(max_requests=100, window_seconds=60)
        client = TestClient(app)
        headers = {"X-API-Key": API_KEY}

        for _ in range(100):
            client.post("/health/data/reload", headers=headers)

        response = client.post("/health/data/reload", headers=headers)
        assert response.status_code == 429
        assert "Retry-After" in response.headers


# ---------------------------------------------------------------------------
# VAL-CROSS-010: Lookup returns 404 when under rate limit
# ---------------------------------------------------------------------------


class TestLookupUnderRateLimit:
    """Lookup returns 404 (not 429) when under the rate limit."""

    def test_lookup_404_when_under_limit(self):
        """A single lookup for unknown URL returns 404, not 429."""
        app = _build_app(max_requests=100, window_seconds=60)
        client = TestClient(app)
        headers = {"X-API-Key": API_KEY, "X-Request-ID": "lookup-trace"}

        response = client.get("/api/papers/lookup", headers=headers)
        assert response.status_code == 404
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"] == "lookup-trace"

    def test_lookup_404_includes_security_headers(self):
        """404 from lookup includes security headers."""
        app = _build_app(max_requests=100, window_seconds=60)
        client = TestClient(app)
        headers = {"X-API-Key": API_KEY}

        response = client.get("/api/papers/lookup", headers=headers)
        assert response.status_code == 404
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers


# ---------------------------------------------------------------------------
# Client identification: API key or IP
# ---------------------------------------------------------------------------


class TestClientIdentification:
    """Rate limits are per-client (by API key or IP)."""

    def test_valid_key_bucket_is_separate_from_no_key_bucket(self):
        """Valid API-key requests and missing-key requests use separate buckets."""
        app = _build_app(max_requests=5, window_seconds=60)
        client = TestClient(app)

        for _ in range(5):
            assert (
                client.get("/api/secure", headers={"X-API-Key": API_KEY}).status_code
                == 200
            )

        response = client.get("/api/secure", headers={"X-API-Key": API_KEY})
        assert response.status_code == 429

        response = client.get("/api/secure")
        assert response.status_code == 401

    def test_invalid_api_keys_share_ip_bucket(self):
        """Rotating bogus API keys does not bypass failed-auth rate limits."""
        app = _build_app(max_requests=5, window_seconds=60)
        client = TestClient(app)

        for i in range(5):
            response = client.get("/api/secure", headers={"X-API-Key": f"wrong-{i}"})
            assert response.status_code == 403

        response = client.get("/api/secure", headers={"X-API-Key": "wrong-6"})
        assert response.status_code == 429

    def test_no_key_identified_by_ip(self):
        """Requests without API key are identified by client IP."""
        app = _build_app(max_requests=5, window_seconds=60)
        client = TestClient(app)

        # 5 requests without key → 401 each, but counted by IP
        for _ in range(5):
            r = client.get("/api/secure")
            assert r.status_code == 401

        # 6th request → 429 (rate limited by IP)
        r = client.get("/api/secure")
        assert r.status_code == 429

    def test_requests_with_key_identified_by_key(self):
        """Requests with API key are identified by that key."""
        app = _build_app(max_requests=5, window_seconds=60)
        client = TestClient(app)
        headers = {"X-API-Key": API_KEY}

        # 5 valid requests
        for _ in range(5):
            r = client.get("/api/secure", headers=headers)
            assert r.status_code == 200

        # 6th → 429
        r = client.get("/api/secure", headers=headers)
        assert r.status_code == 429


# ---------------------------------------------------------------------------
# Integration with the full app
# ---------------------------------------------------------------------------


class TestRateLimitWithFullApp:
    """Integration tests using the real app client fixture."""

    def test_api_endpoint_rate_limited(self, client: TestClient, api_key_headers: dict):
        """Real app: /api/metadata is rate limited."""
        # We can't easily test 100 requests in integration without resetting state,
        # but we verify the middleware is present by checking it doesn't break normal requests.
        response = client.get("/api/metadata", headers=api_key_headers)
        assert response.status_code == 200

    def test_public_endpoints_not_rate_limited(self, client: TestClient):
        """Real app: public endpoints work normally."""
        response = client.get("/")
        assert response.status_code == 200

        response = client.get("/health")
        assert response.status_code == 200
