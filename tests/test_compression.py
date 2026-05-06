"""
Tests for Gzip Response Compression Middleware.

Validates:
- Large responses (>1KB) are compressed when client sends Accept-Encoding: gzip (VAL-SEC-006)
- Compressed body is smaller than uncompressed original (VAL-SEC-006)
- Small responses (<1KB) are NOT compressed (VAL-SEC-007)
- Requests without Accept-Encoding receive uncompressed responses (VAL-SEC-014)
- Security headers remain present on compressed responses (VAL-SEC-012)
- Compressed filtered result sets decompress correctly (VAL-CROSS-005)

NOTE: httpx / TestClient transparently decompresses gzip responses, so
``response.content`` always returns *decompressed* bytes.  We verify
compression via the ``Content-Encoding`` and ``Content-Length`` headers
instead of trying to read the raw compressed wire bytes.
"""

import pytest
from fastapi.testclient import TestClient

from app_v2.middleware.compression import MINIMUM_SIZE

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

#: Request headers that explicitly request gzip.
GZIP_HEADERS = {"Accept-Encoding": "gzip, deflate, br"}

#: Request headers that explicitly decline gzip (identity only).
NO_GZIP_HEADERS = {"Accept-Encoding": "identity"}

SECURITY_HEADERS = [
    "X-Content-Type-Options",
    "X-Frame-Options",
    "X-XSS-Protection",
    "Strict-Transport-Security",
    "Referrer-Policy",
    "Permissions-Policy",
    "Content-Security-Policy",
]


def _assert_compression_matches_size(response, uncompressed_body: bytes) -> None:
    """Compression depends on the actual payload size, not endpoint identity."""
    if len(uncompressed_body) >= MINIMUM_SIZE:
        assert response.headers.get("content-encoding") == "gzip"
    else:
        assert response.headers.get("content-encoding") != "gzip"


# ---------------------------------------------------------------------------
# VAL-SEC-006: Compression reduces response size for large payloads
# ---------------------------------------------------------------------------


class TestCompressionLargePayload:
    """Large responses (>1KB) must be gzip-compressed when client accepts it."""

    def test_large_response_has_content_encoding_gzip(
        self, client: TestClient, api_key_headers: dict
    ):
        """Large response with Accept-Encoding: gzip must include Content-Encoding: gzip."""
        response = client.get(
            "/api/papers",
            headers={**api_key_headers, **GZIP_HEADERS},
        )
        assert response.status_code == 200
        assert (
            response.headers.get("content-encoding") == "gzip"
        ), "Expected Content-Encoding: gzip for large response"

    def test_compressed_content_length_smaller_than_body(
        self, client: TestClient, api_key_headers: dict
    ):
        """Content-Length (compressed) must be smaller than decompressed body size."""
        response = client.get(
            "/api/papers",
            headers={**api_key_headers, **GZIP_HEADERS},
        )
        assert response.status_code == 200
        assert response.headers.get("content-encoding") == "gzip"

        content_length = int(response.headers["content-length"])
        decompressed_size = len(response.content)

        assert content_length < decompressed_size, (
            f"Compressed Content-Length ({content_length}B) should be smaller than "
            f"decompressed body ({decompressed_size}B)"
        )

    def test_compressed_body_decompresses_to_valid_json(
        self, client: TestClient, api_key_headers: dict
    ):
        """httpx auto-decompresses — verify the JSON matches the uncompressed response.

        execution_time_ms varies between requests so we exclude it from comparison.
        """
        # Uncompressed (identity)
        uncompressed = client.get(
            "/api/papers",
            headers={**api_key_headers, **NO_GZIP_HEADERS},
        )
        expected_data = uncompressed.json()

        # Compressed — httpx auto-decompresses so .json() works directly
        compressed = client.get(
            "/api/papers",
            headers={**api_key_headers, **GZIP_HEADERS},
        )
        assert compressed.headers.get("content-encoding") == "gzip"
        actual_data = compressed.json()

        # Compare paper data (exclude timing which varies between requests)
        assert actual_data["papers"] == expected_data["papers"]
        assert actual_data["total"] == expected_data["total"]
        assert actual_data["pagination"] == expected_data["pagination"]


# ---------------------------------------------------------------------------
# VAL-SEC-007: Small responses are not compressed
# ---------------------------------------------------------------------------


class TestNoCompressionSmallPayload:
    """Small responses (<1KB) must NOT be compressed."""

    def test_small_response_not_compressed(
        self, client: TestClient, api_key_headers: dict
    ):
        """Small response must not include Content-Encoding: gzip."""
        # The root endpoint "/" returns a small JSON (< 1KB)
        response = client.get("/", headers=GZIP_HEADERS)
        assert response.status_code == 200
        assert (
            response.headers.get("content-encoding") != "gzip"
        ), "Small response should not be compressed"

    def test_small_api_response_not_compressed(
        self, client: TestClient, api_key_headers: dict
    ):
        """Even a small API response should not be compressed."""
        # /api endpoint returns a small info JSON
        response = client.get(
            "/api",
            headers={**api_key_headers, **GZIP_HEADERS},
        )
        assert response.status_code == 200
        assert (
            response.headers.get("content-encoding") != "gzip"
        ), "Small API response should not be compressed"


# ---------------------------------------------------------------------------
# VAL-SEC-014: Compression skipped when client omits Accept-Encoding
# ---------------------------------------------------------------------------


class TestNoCompressionWithoutAcceptEncoding:
    """Requests without Accept-Encoding: gzip must receive uncompressed responses."""

    def test_large_response_without_gzip_not_compressed(
        self, client: TestClient, api_key_headers: dict
    ):
        """Large response without gzip in Accept-Encoding must not be compressed."""
        response = client.get(
            "/api/papers",
            headers={**api_key_headers, **NO_GZIP_HEADERS},
        )
        assert response.status_code == 200
        assert (
            response.headers.get("content-encoding") != "gzip"
        ), "Response should not be compressed when client doesn't accept gzip"

    def test_large_response_is_valid_json(
        self, client: TestClient, api_key_headers: dict
    ):
        """Uncompressed large response must be valid JSON."""
        response = client.get(
            "/api/papers",
            headers={**api_key_headers, **NO_GZIP_HEADERS},
        )
        assert response.status_code == 200
        data = response.json()
        assert "papers" in data
        assert isinstance(data["papers"], list)


# ---------------------------------------------------------------------------
# VAL-SEC-012: Security headers on compressed responses
# ---------------------------------------------------------------------------


class TestSecurityHeadersOnCompressedResponses:
    """Security headers must be present on compressed responses."""

    def test_security_headers_present_on_compressed_response(
        self, client: TestClient, api_key_headers: dict
    ):
        """All seven security headers must be present on a compressed response."""
        response = client.get(
            "/api/papers",
            headers={**api_key_headers, **GZIP_HEADERS},
        )
        assert response.status_code == 200
        assert response.headers.get("content-encoding") == "gzip"

        for header in SECURITY_HEADERS:
            assert (
                header in response.headers
            ), f"Security header '{header}' missing from compressed response"

    def test_security_headers_present_on_uncompressed_response(
        self, client: TestClient, api_key_headers: dict
    ):
        """Security headers must also be present on uncompressed responses."""
        response = client.get(
            "/api/papers",
            headers={**api_key_headers, **NO_GZIP_HEADERS},
        )
        assert response.status_code == 200

        for header in SECURITY_HEADERS:
            assert (
                header in response.headers
            ), f"Security header '{header}' missing from uncompressed response"


# ---------------------------------------------------------------------------
# VAL-CROSS-005: Compressed filtered result sets are correct
# ---------------------------------------------------------------------------


class TestCompressedFilteredResults:
    """Compressed responses for filtered result sets must decompress to correct data."""

    def test_program_abbrev_filter_compressed_correctly(
        self, client: TestClient, api_key_headers: dict
    ):
        """GET /api/papers?program_abbrev=ICS compressed result must decompress correctly."""
        # Uncompressed
        uncompressed = client.get(
            "/api/papers?program_abbrev=ICS",
            headers={**api_key_headers, **NO_GZIP_HEADERS},
        )
        assert uncompressed.status_code == 200
        expected = uncompressed.json()

        # Compressed (httpx auto-decompresses)
        compressed = client.get(
            "/api/papers?program_abbrev=ICS",
            headers={**api_key_headers, **GZIP_HEADERS},
        )
        assert compressed.status_code == 200
        _assert_compression_matches_size(compressed, uncompressed.content)
        actual = compressed.json()

        # Compare papers (exclude execution_time_ms which varies)
        assert actual["papers"] == expected["papers"]
        assert actual["total"] == expected["total"]
        # Verify the filter actually worked
        if expected["total"] > 0:
            for paper in actual["papers"]:
                assert paper["program_abbrev"] == "ICS"

    def test_search_filter_compressed_correctly(
        self, client: TestClient, api_key_headers: dict
    ):
        """GET /api/papers?search=... compressed result must decompress correctly."""
        # Uncompressed
        uncompressed = client.get(
            "/api/papers?search=algorithm",
            headers={**api_key_headers, **NO_GZIP_HEADERS},
        )
        assert uncompressed.status_code == 200
        expected = uncompressed.json()

        # Compressed
        compressed = client.get(
            "/api/papers?search=algorithm",
            headers={**api_key_headers, **GZIP_HEADERS},
        )
        assert compressed.status_code == 200
        _assert_compression_matches_size(compressed, uncompressed.content)
        actual = compressed.json()
        # Compare papers (exclude execution_time_ms which varies)
        assert actual["papers"] == expected["papers"]
        assert actual["total"] == expected["total"]

    def test_metadata_compressed_correctly(
        self, client: TestClient, api_key_headers: dict
    ):
        """GET /api/metadata compressed result must decompress correctly."""
        # Uncompressed
        uncompressed = client.get(
            "/api/metadata",
            headers={**api_key_headers, **NO_GZIP_HEADERS},
        )
        assert uncompressed.status_code == 200
        expected = uncompressed.json()

        # Compressed
        compressed = client.get(
            "/api/metadata",
            headers={**api_key_headers, **GZIP_HEADERS},
        )
        assert compressed.status_code == 200
        _assert_compression_matches_size(compressed, uncompressed.content)
        actual = compressed.json()
        assert actual == expected

    def test_statistics_response_not_compressed_when_small(
        self, client: TestClient, api_key_headers: dict
    ):
        """GET /api/statistics returns a small payload (<1KB) — not compressed."""
        compressed = client.get(
            "/api/statistics",
            headers={**api_key_headers, **GZIP_HEADERS},
        )
        assert compressed.status_code == 200
        # Statistics response is small (<1KB) so should not be compressed
        assert compressed.headers.get("content-encoding") != "gzip"
        data = compressed.json()
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------


class TestCompressionEdgeCases:
    """Edge cases for compression behavior."""

    def test_vary_header_added_on_compressed_response(
        self, client: TestClient, api_key_headers: dict
    ):
        """Compressed responses should include Vary: Accept-Encoding."""
        response = client.get(
            "/api/papers",
            headers={**api_key_headers, **GZIP_HEADERS},
        )
        assert response.status_code == 200
        assert response.headers.get("content-encoding") == "gzip"
        vary = response.headers.get("vary", "")
        assert (
            "Accept-Encoding" in vary
        ), "Vary header should include Accept-Encoding for compressed responses"

    def test_request_id_present_on_compressed_response(
        self, client: TestClient, api_key_headers: dict
    ):
        """X-Request-ID must be present on compressed responses."""
        response = client.get(
            "/api/papers",
            headers={**api_key_headers, **GZIP_HEADERS},
        )
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers

    def test_accept_encoding_deflate_only_no_compression(
        self, client: TestClient, api_key_headers: dict
    ):
        """Only deflate in Accept-Encoding (no gzip) should not trigger compression."""
        response = client.get(
            "/api/papers",
            headers={**api_key_headers, "Accept-Encoding": "deflate, br"},
        )
        assert response.status_code == 200
        assert response.headers.get("content-encoding") != "gzip"

    def test_content_length_matches_compressed_body(
        self, client: TestClient, api_key_headers: dict
    ):
        """Content-Length on compressed response must reflect compressed size.

        httpx auto-decompresses response.content, so we only verify
        Content-Length is present and smaller than the decompressed size.
        """
        response = client.get(
            "/api/papers",
            headers={**api_key_headers, **GZIP_HEADERS},
        )
        assert response.status_code == 200
        assert response.headers.get("content-encoding") == "gzip"

        content_length = int(response.headers["content-length"])
        decompressed_size = len(response.content)
        assert content_length < decompressed_size, (
            f"Content-Length ({content_length}) should be smaller than "
            f"decompressed body ({decompressed_size})"
        )

    def test_health_endpoint_not_compressed(
        self, client: TestClient, api_key_headers: dict
    ):
        """Health endpoint response is small and should not be compressed."""
        response = client.get("/health", headers=GZIP_HEADERS)
        assert response.status_code == 200
        assert response.headers.get("content-encoding") != "gzip"

    def test_year_endpoint_compressed_correctly(
        self, client: TestClient, api_key_headers: dict
    ):
        """Year-filtered endpoint compressed result must decompress correctly."""
        # Get a year with papers
        meta = client.get("/api/metadata", headers=api_key_headers)
        years = meta.json().get("years", [])
        if not years:
            pytest.skip("No years available in data")

        year = years[0]
        uncompressed = client.get(
            f"/api/papers/year/{year}",
            headers={**api_key_headers, **NO_GZIP_HEADERS},
        )
        expected = uncompressed.json()

        compressed = client.get(
            f"/api/papers/year/{year}",
            headers={**api_key_headers, **GZIP_HEADERS},
        )
        assert compressed.status_code == 200
        # Only check compression if body is large enough
        if compressed.headers.get("content-encoding") == "gzip":
            actual = compressed.json()
            assert actual["papers"] == expected["papers"]
            assert actual["total"] == expected["total"]
