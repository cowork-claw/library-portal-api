"""
Tests for Structured JSON Logging.

Validates:
- VAL-SEC-008: JSON logging format contains required fields (timestamp, level, name, message, request_id)
- VAL-SEC-011: Request ID in structured JSON log matches the X-Request-ID from request/response
- VAL-CROSS-011: Structured log emitted on 429 response with request_id, path, and status_code

Also covers:
- Log lines are valid JSON when structured logging is active
- Each JSON log contains timestamp, level, name, message, request_id
- request_id in logs matches the X-Request-ID from the request/response
- 429 responses emit a structured log line with status_code 429
"""

import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app_v2.middleware.auth import APIKeyMiddleware
from app_v2.middleware.security import SecurityHeadersMiddleware
from app_v2.middleware.structured_logging import (
    RequestIDLogFilter,
    RequestIDMiddleware,
    StructuredJSONFormatter,
    StructuredLoggingMiddleware,
    current_request_id,
    setup_structured_logging,
)

API_KEY = "test-key"


@pytest.fixture(autouse=True)
def _restore_root_logger():
    """Prevent root logger handlers and levels from leaking across tests."""
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level
    yield
    root_logger.handlers[:] = original_handlers
    root_logger.setLevel(original_level)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _LogCapture(logging.Handler):
    """Simple handler that captures formatted log lines into a list."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)
        self.messages.append(self.format(record))


def _build_app_with_logging() -> tuple[FastAPI, _LogCapture]:
    """Build a FastAPI app with structured logging and capture handler."""
    app = FastAPI()

    # Add a capture handler to the root logger
    capture = _LogCapture()
    capture.setFormatter(StructuredJSONFormatter())
    capture.addFilter(RequestIDLogFilter())
    root_logger = logging.getLogger()
    root_logger.addHandler(capture)
    root_logger.setLevel(logging.DEBUG)

    # Middleware registered in reverse order (last = outermost)
    # Execution order: RequestID -> StructuredLogging -> SecurityHeaders -> APIKey -> Routes
    app.add_middleware(APIKeyMiddleware, api_key=API_KEY, environment="production")
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(StructuredLoggingMiddleware)
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

    return app, capture


def _build_app_with_429() -> tuple[FastAPI, _LogCapture]:
    """Build a FastAPI app that simulates a 429 response for testing."""
    from typing import Callable

    from fastapi import Request, Response
    from fastapi.responses import JSONResponse
    from starlette.middleware.base import BaseHTTPMiddleware as BaseMW

    app = FastAPI()

    capture = _LogCapture()
    capture.setFormatter(StructuredJSONFormatter())
    capture.addFilter(RequestIDLogFilter())
    root_logger = logging.getLogger()
    root_logger.addHandler(capture)
    root_logger.setLevel(logging.DEBUG)

    class _RateLimitSimulator(BaseMW):
        """Simulates rate limiting by returning 429 on the second request."""

        def __init__(self, app):
            super().__init__(app)
            self.request_count = 0

        async def dispatch(self, request: Request, call_next: Callable) -> Response:
            self.request_count += 1
            if self.request_count > 1:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests"},
                    headers={"Retry-After": "60"},
                )
            return await call_next(request)

    # Execution: RequestID -> StructuredLogging -> RateLimitSim -> Routes
    app.add_middleware(_RateLimitSimulator)
    app.add_middleware(StructuredLoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/api/test")
    def test_endpoint():
        return {"status": "ok"}

    return app, capture


# ---------------------------------------------------------------------------
# Test: VAL-SEC-008 — JSON logging format contains required fields
# ---------------------------------------------------------------------------


class TestStructuredLogFormat:
    """Every structured log line must be valid JSON with required fields."""

    def test_log_line_is_valid_json(self):
        """Log lines emitted during a request are valid JSON."""
        app, capture = _build_app_with_logging()
        client = TestClient(app)

        response = client.get("/")
        assert response.status_code == 200

        # At least one log line should have been emitted
        assert len(capture.messages) > 0

        for msg in capture.messages:
            parsed = json.loads(msg)
            assert isinstance(parsed, dict)

    def test_log_line_has_required_fields(self):
        """Each JSON log line contains timestamp, level, name, message, request_id."""
        app, capture = _build_app_with_logging()
        client = TestClient(app)

        response = client.get("/")
        assert response.status_code == 200

        required_fields = {"timestamp", "level", "name", "message", "request_id"}
        for msg in capture.messages:
            parsed = json.loads(msg)
            missing = required_fields - set(parsed.keys())
            assert not missing, f"Missing fields: {missing} in log: {msg}"

    def test_timestamp_format(self):
        """Timestamp field is a valid ISO-8601 string."""
        app, capture = _build_app_with_logging()
        client = TestClient(app)

        response = client.get("/")
        assert response.status_code == 200

        for msg in capture.messages:
            parsed = json.loads(msg)
            ts = parsed["timestamp"]
            # Should be parseable as ISO format
            assert "T" in ts, f"Timestamp missing T separator: {ts}"
            # Should contain timezone info
            assert "+" in ts or ts.endswith("Z"), f"Timestamp missing tz: {ts}"

    def test_level_is_valid(self):
        """Level field is a valid log level name."""
        app, capture = _build_app_with_logging()
        client = TestClient(app)

        response = client.get("/")
        assert response.status_code == 200

        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        for msg in capture.messages:
            parsed = json.loads(msg)
            assert parsed["level"] in valid_levels, f"Invalid level: {parsed['level']}"

    def test_request_id_field_is_string(self):
        """request_id field is a string."""
        app, capture = _build_app_with_logging()
        client = TestClient(app)

        response = client.get("/")
        assert response.status_code == 200

        for msg in capture.messages:
            parsed = json.loads(msg)
            assert isinstance(
                parsed["request_id"], str
            ), f"request_id not string: {parsed['request_id']}"


# ---------------------------------------------------------------------------
# Test: VAL-SEC-011 — Request ID appears in log output
# ---------------------------------------------------------------------------


class TestRequestIDInLogs:
    """request_id in structured logs must match the X-Request-ID from the response."""

    def test_request_id_in_logs_matches_response_header(self):
        """request_id in access log lines matches X-Request-ID from the response."""
        app, capture = _build_app_with_logging()
        client = TestClient(app)

        custom_id = "trace-abc-123"
        response = client.get("/", headers={"X-Request-ID": custom_id})
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == custom_id

        # Access log lines (from app_v2.access logger) should have the matching request_id
        access_logs = [
            json.loads(msg)
            for msg in capture.messages
            if json.loads(msg).get("name") == "app_v2.access"
        ]
        assert len(access_logs) > 0, "No access log lines found"
        for log_entry in access_logs:
            assert (
                log_entry["request_id"] == custom_id
            ), f"Expected request_id={custom_id}, got {log_entry['request_id']}"

        # No log line during the request should have a different non-"-" request_id
        for msg in capture.messages:
            parsed = json.loads(msg)
            rid = parsed["request_id"]
            if rid != "-":
                assert (
                    rid == custom_id
                ), f"Log line has unexpected request_id={rid}, expected {custom_id}"

    def test_generated_request_id_in_logs(self):
        """When no X-Request-ID is provided, generated ID appears in logs."""
        app, capture = _build_app_with_logging()
        client = TestClient(app)

        response = client.get("/")
        assert response.status_code == 200

        response_request_id = response.headers["X-Request-ID"]
        assert response_request_id  # non-empty

        # Log lines should contain the generated request ID
        found_matching = False
        for msg in capture.messages:
            parsed = json.loads(msg)
            if parsed["request_id"] == response_request_id:
                found_matching = True
                break

        assert found_matching, (
            f"No log line with request_id={response_request_id}. "
            f"IDs in logs: {[json.loads(m)['request_id'] for m in capture.messages]}"
        )

    def test_different_requests_get_different_ids_in_logs(self):
        """Two sequential requests get different request IDs in their access log lines."""
        app, capture = _build_app_with_logging()
        client = TestClient(app)

        # First request
        response1 = client.get("/", headers={"X-Request-ID": "req-001"})
        assert response1.status_code == 200

        # Clear capture
        capture.messages.clear()
        capture.records.clear()

        # Second request
        response2 = client.get("/", headers={"X-Request-ID": "req-002"})
        assert response2.status_code == 200

        # Access log lines should have req-002
        access_logs = [
            json.loads(msg)
            for msg in capture.messages
            if json.loads(msg).get("name") == "app_v2.access"
        ]
        assert len(access_logs) > 0
        for log_entry in access_logs:
            assert log_entry["request_id"] == "req-002"


# ---------------------------------------------------------------------------
# Test: VAL-CROSS-011 — Structured log on 429 response
# ---------------------------------------------------------------------------


class TestStructuredLogOn429:
    """429 responses must emit a structured JSON log line with request_id, path, and status_code: 429."""

    def test_429_emits_structured_log(self):
        """When a 429 response is returned, a structured log line is emitted."""
        app, capture = _build_app_with_429()
        client = TestClient(app)

        # First request should succeed (200)
        response1 = client.get("/api/test", headers={"X-Request-ID": "throttle-test"})
        assert response1.status_code == 200

        # Clear capture for the 429 request
        capture.messages.clear()
        capture.records.clear()

        # Second request should be rate limited (429)
        response2 = client.get("/api/test", headers={"X-Request-ID": "throttle-test"})
        assert response2.status_code == 429

        # Find the access log line with status_code 429
        access_logs = []
        for msg in capture.messages:
            parsed = json.loads(msg)
            if parsed.get("status_code") == 429:
                access_logs.append(parsed)

        assert len(access_logs) > 0, (
            "Expected at least one structured log line with status_code 429. "
            f"Got: {capture.messages}"
        )

    def test_429_log_contains_request_id(self):
        """429 log line contains the correct request_id."""
        app, capture = _build_app_with_429()
        client = TestClient(app)

        custom_id = "rate-limit-trace-999"
        # First request succeeds
        client.get("/api/test", headers={"X-Request-ID": custom_id})
        capture.messages.clear()
        capture.records.clear()

        # Second request returns 429
        response = client.get("/api/test", headers={"X-Request-ID": custom_id})
        assert response.status_code == 429

        # Find 429 access log
        found = False
        for msg in capture.messages:
            parsed = json.loads(msg)
            if parsed.get("status_code") == 429:
                assert (
                    parsed["request_id"] == custom_id
                ), f"request_id mismatch: expected {custom_id}, got {parsed['request_id']}"
                found = True

        assert found, "No 429 log line found"

    def test_429_log_contains_path(self):
        """429 log line contains the request path."""
        app, capture = _build_app_with_429()
        client = TestClient(app)

        # First request succeeds
        client.get("/api/test", headers={"X-Request-ID": "path-test"})
        capture.messages.clear()
        capture.records.clear()

        # Second request returns 429
        response = client.get("/api/test", headers={"X-Request-ID": "path-test"})
        assert response.status_code == 429

        # Find 429 access log
        found = False
        for msg in capture.messages:
            parsed = json.loads(msg)
            if parsed.get("status_code") == 429:
                assert (
                    parsed.get("path") == "/api/test"
                ), f"Path mismatch: expected /api/test, got {parsed.get('path')}"
                found = True

        assert found, "No 429 log line found"


# ---------------------------------------------------------------------------
# Test: Formatter unit tests
# ---------------------------------------------------------------------------


class TestStructuredJSONFormatter:
    """Unit tests for the StructuredJSONFormatter."""

    def test_formatter_output_is_valid_json(self):
        """Formatter output is valid JSON."""
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.request_id = "test-req-id"  # type: ignore[attr-defined]

        output = formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_formatter_includes_all_required_fields(self):
        """Formatter includes timestamp, level, name, message, request_id."""
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Warning message",
            args=(),
            exc_info=None,
        )
        record.request_id = "req-abc-123"  # type: ignore[attr-defined]

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "timestamp" in parsed
        assert parsed["level"] == "WARNING"
        assert parsed["name"] == "test.logger"
        assert parsed["message"] == "Warning message"
        assert parsed["request_id"] == "req-abc-123"

    def test_formatter_with_default_request_id(self):
        """When no request_id set, defaults to '-'."""
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="No request context",
            args=(),
            exc_info=None,
        )
        # Don't set request_id attribute

        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["request_id"] == "-"

    def test_formatter_with_extra_fields(self):
        """Extra fields like method, path, status_code are included."""
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="app_v2.access",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="GET /api/test 200",
            args=(),
            exc_info=None,
        )
        record.request_id = "req-id"  # type: ignore[attr-defined]
        record.method = "GET"  # type: ignore[attr-defined]
        record.path = "/api/test"  # type: ignore[attr-defined]
        record.status_code = 200  # type: ignore[attr-defined]

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["method"] == "GET"
        assert parsed["path"] == "/api/test"
        assert parsed["status_code"] == 200
        assert parsed["message"] == "GET /api/test 200"


# ---------------------------------------------------------------------------
# Test: Integration with full app
# ---------------------------------------------------------------------------


class TestStructuredLoggingWithFullApp:
    """Integration tests using the real app client fixture."""

    def test_structured_log_on_api_request(
        self, client: TestClient, api_key_headers: dict
    ):
        """Real app: requesting /api/papers produces structured log output."""
        # Set up a capture handler with structured formatter
        capture = _LogCapture()
        capture.setFormatter(StructuredJSONFormatter())
        capture.addFilter(RequestIDLogFilter())
        root_logger = logging.getLogger()
        root_logger.addHandler(capture)

        try:
            custom_id = "full-app-trace"
            headers = {**api_key_headers, "X-Request-ID": custom_id}
            response = client.get("/api/papers", headers=headers)
            assert response.status_code == 200
            assert response.headers["X-Request-ID"] == custom_id

            # Verify log output is JSON with correct request_id
            found_matching = False
            for msg in capture.messages:
                parsed = json.loads(msg)
                assert "timestamp" in parsed
                assert "level" in parsed
                assert "name" in parsed
                assert "message" in parsed
                assert "request_id" in parsed
                if parsed["request_id"] == custom_id:
                    found_matching = True

            assert found_matching, (
                f"No log with request_id={custom_id}. "
                f"IDs: {[json.loads(m)['request_id'] for m in capture.messages]}"
            )
        finally:
            root_logger.removeHandler(capture)

    def test_structured_log_on_401(self, client: TestClient):
        """Real app: 401 response produces structured log with request_id."""
        capture = _LogCapture()
        capture.setFormatter(StructuredJSONFormatter())
        capture.addFilter(RequestIDLogFilter())
        root_logger = logging.getLogger()
        root_logger.addHandler(capture)

        try:
            custom_id = "auth-fail-trace"
            response = client.get("/api/papers", headers={"X-Request-ID": custom_id})
            assert response.status_code == 401
            assert response.headers["X-Request-ID"] == custom_id

            # Verify structured logs contain the request_id
            found = False
            for msg in capture.messages:
                parsed = json.loads(msg)
                if parsed["request_id"] == custom_id:
                    found = True
                    break

            assert found, (
                f"No log with request_id={custom_id}. "
                f"IDs: {[json.loads(m)['request_id'] for m in capture.messages]}"
            )
        finally:
            root_logger.removeHandler(capture)

    def test_structured_log_on_lookup_404(
        self, client: TestClient, api_key_headers: dict
    ):
        """Real app: 404 from lookup produces structured log with request_id."""
        capture = _LogCapture()
        capture.setFormatter(StructuredJSONFormatter())
        capture.addFilter(RequestIDLogFilter())
        root_logger = logging.getLogger()
        root_logger.addHandler(capture)

        try:
            custom_id = "lookup-404-trace"
            headers = {**api_key_headers, "X-Request-ID": custom_id}
            response = client.get(
                "/api/papers/lookup?url=https://example.com/nonexistent.pdf",
                headers=headers,
            )
            assert response.status_code == 404
            assert response.headers["X-Request-ID"] == custom_id

            found = False
            for msg in capture.messages:
                parsed = json.loads(msg)
                if parsed["request_id"] == custom_id:
                    found = True
                    break

            assert found
        finally:
            root_logger.removeHandler(capture)


# ---------------------------------------------------------------------------
# Test: setup_structured_logging function
# ---------------------------------------------------------------------------


class TestSetupStructuredLogging:
    """Tests for the setup_structured_logging() configuration function."""

    def test_setup_configures_root_logger(self):
        """setup_structured_logging() configures the root logger with JSON handler."""
        setup_structured_logging("INFO")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

        # Check that at least one handler has our formatter
        has_structured = False
        for handler in root_logger.handlers:
            if isinstance(handler.formatter, StructuredJSONFormatter):
                has_structured = True
                break

        assert has_structured, "No handler with StructuredJSONFormatter found"

    def test_setup_respects_log_level(self):
        """setup_structured_logging() respects the provided log level."""
        setup_structured_logging("DEBUG")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

        setup_structured_logging("WARNING")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING

    def test_context_var_default(self):
        """ContextVar default value is '-' when no request context."""
        assert current_request_id.get("-") == "-"
