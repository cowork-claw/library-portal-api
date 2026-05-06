"""
Tests for GET /api/papers/lookup?url=<paper_url> endpoint.

Covers validation contract assertions:
- VAL-USABILITY-014: returns correct paper for a valid URL
- VAL-USABILITY-015: returns 404 for unknown URL
- VAL-USABILITY-016: rejects missing url parameter
- VAL-USABILITY-017: rejects malformed URL format
- VAL-USABILITY-018: endpoint appears in OpenAPI schema with documented url parameter
"""

import json

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_PAPERS = [
    {
        "file_name": "cs101-midterm.pdf",
        "url": "https://example.com/papers/cs101-midterm.pdf",
        "year": 2024,
        "semester": 1,
        "course_code": "CS101",
        "course_name": "Data Structures",
        "degree_type": "B.Tech",
        "program_abbrev": "CSE",
        "program": "B.Tech Computer Science",
        "streams": ["cs"],
        "paper_type": "Regular",
    },
    {
        "file_name": "cs201-final.pdf",
        "url": "https://example.com/papers/cs201-final.pdf",
        "year": 2024,
        "semester": 2,
        "course_code": "CS201",
        "course_name": "Algorithms",
        "degree_type": "B.Tech",
        "program_abbrev": "CSE",
        "program": "B.Tech Computer Science",
        "streams": ["cs"],
        "paper_type": "Regular",
    },
    {
        "file_name": "ee101-quiz.pdf",
        "url": "https://example.com/papers/ee101-quiz.pdf",
        "year": 2023,
        "semester": 1,
        "course_code": "EE101",
        "course_name": "Circuits",
        "degree_type": "B.Tech",
        "program_abbrev": "ECE",
        "program": "B.Tech Electronics",
        "streams": ["core"],
        "paper_type": "Makeup",
    },
]


@pytest.fixture()
def client_with_papers(tmp_path, monkeypatch):
    """Create a TestClient with sample papers loaded from a temp directory."""
    import importlib
    import os

    import config.config_v2 as config_module

    # Write sample papers in DataLoader format: {course_code: [papers...]}
    data_dir = tmp_path / "organized"
    data_dir.mkdir()
    data_dict = {}
    for p in SAMPLE_PAPERS:
        cc = p["course_code"]
        data_dict.setdefault(cc, []).append(p)
    data_file = data_dir / "papers.json"
    data_file.write_text(json.dumps(data_dict))

    os.environ["LIBRARY_PORTAL_API_KEY"] = "test-key"
    os.environ["LIBRARY_PORTAL_DATA_DIRECTORY"] = str(data_dir)
    monkeypatch.setattr(config_module.settings, "DATA_DIRECTORY", data_dir)

    import app_v2.main as main_module

    importlib.reload(main_module)

    with TestClient(main_module.app) as c:
        yield c


def _auth_headers():
    return {"X-API-Key": "test-key"}


# ---------------------------------------------------------------------------
# VAL-USABILITY-014: Lookup returns correct paper for a valid URL
# ---------------------------------------------------------------------------


class TestLookupValidURL:
    """GET /api/papers/lookup returns the correct paper for a known URL."""

    def test_returns_200_for_known_url(self, client_with_papers):
        known_url = "https://example.com/papers/cs101-midterm.pdf"
        resp = client_with_papers.get(
            "/api/papers/lookup",
            params={"url": known_url},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200

    def test_returns_single_paper_object(self, client_with_papers):
        known_url = "https://example.com/papers/cs101-midterm.pdf"
        resp = client_with_papers.get(
            "/api/papers/lookup",
            params={"url": known_url},
            headers=_auth_headers(),
        )
        body = resp.json()
        # Response should be a single Paper object (dict), not a list
        assert isinstance(body, dict)
        assert "papers" not in body  # Not a paginated response

    def test_url_field_matches_exactly(self, client_with_papers):
        known_url = "https://example.com/papers/cs101-midterm.pdf"
        resp = client_with_papers.get(
            "/api/papers/lookup",
            params={"url": known_url},
            headers=_auth_headers(),
        )
        body = resp.json()
        assert body["url"] == known_url

    def test_paper_has_expected_fields(self, client_with_papers):
        known_url = "https://example.com/papers/cs101-midterm.pdf"
        resp = client_with_papers.get(
            "/api/papers/lookup",
            params={"url": known_url},
            headers=_auth_headers(),
        )
        body = resp.json()
        assert body["course_code"] == "CS101"
        assert body["year"] == 2024
        assert body["semester"] == 1

    def test_returns_correct_paper_for_different_urls(self, client_with_papers):
        """Verify that each URL returns the correct distinct paper."""
        for paper_data in SAMPLE_PAPERS:
            resp = client_with_papers.get(
                "/api/papers/lookup",
                params={"url": paper_data["url"]},
                headers=_auth_headers(),
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["url"] == paper_data["url"]
            assert body["course_code"] == paper_data["course_code"]

    def test_strips_internal_fields(self, client_with_papers):
        """Verify that internal fields (prefixed with _) are not returned."""
        known_url = "https://example.com/papers/cs101-midterm.pdf"
        resp = client_with_papers.get(
            "/api/papers/lookup",
            params={"url": known_url},
            headers=_auth_headers(),
        )
        body = resp.json()
        for key in body:
            assert not key.startswith("_"), f"Internal field {key!r} leaked in response"


# ---------------------------------------------------------------------------
# VAL-USABILITY-015: Lookup returns 404 for unknown URL
# ---------------------------------------------------------------------------


class TestLookupUnknownURL:
    """GET /api/papers/lookup returns 404 for an unknown URL."""

    def test_returns_404_for_unknown_url(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers/lookup",
            params={"url": "https://example.com/papers/nonexistent.pdf"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 404

    def test_404_response_has_detail(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers/lookup",
            params={"url": "https://example.com/papers/nonexistent.pdf"},
            headers=_auth_headers(),
        )
        body = resp.json()
        assert "detail" in body

    def test_404_for_valid_http_url_not_in_index(self, client_with_papers):
        """Even a valid-looking URL returns 404 if not in the index."""
        resp = client_with_papers.get(
            "/api/papers/lookup",
            params={"url": "https://unknown-site.com/paper.pdf"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# VAL-USABILITY-016: Missing url parameter returns 422
# ---------------------------------------------------------------------------


class TestLookupMissingURL:
    """GET /api/papers/lookup without url parameter returns 422."""

    def test_missing_url_returns_422(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers/lookup",
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    def test_422_error_references_url(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers/lookup",
            headers=_auth_headers(),
        )
        body = resp.json()
        assert "detail" in body
        # Pydantic/FastAPI validation errors reference the field name
        error_locs = [e["loc"] for e in body["detail"]]
        assert any("url" in str(loc) for loc in error_locs)


# ---------------------------------------------------------------------------
# VAL-USABILITY-017: Malformed URL format returns 422
# ---------------------------------------------------------------------------


class TestLookupMalformedURL:
    """GET /api/papers/lookup with malformed URL returns 422."""

    @pytest.mark.parametrize(
        "invalid_url",
        [
            "not-a-url",
            "ftp://example.com/paper.pdf",
            "//example.com/paper.pdf",
            "just-words-here",
        ],
    )
    def test_non_http_url_returns_422(self, client_with_papers, invalid_url):
        resp = client_with_papers.get(
            "/api/papers/lookup",
            params={"url": invalid_url},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    def test_empty_url_returns_422(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers/lookup",
            params={"url": ""},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# VAL-USABILITY-018: Endpoint appears in OpenAPI schema
# ---------------------------------------------------------------------------


class TestLookupOpenAPISchema:
    """The lookup endpoint is documented in the OpenAPI schema."""

    def test_lookup_in_openapi_schema(self, client_with_papers):
        resp = client_with_papers.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()

        # Find the lookup path
        assert "/api/papers/lookup" in schema["paths"]
        lookup_path = schema["paths"]["/api/papers/lookup"]
        assert "get" in lookup_path

    def test_url_parameter_documented(self, client_with_papers):
        resp = client_with_papers.get("/openapi.json")
        schema = resp.json()

        get_op = schema["paths"]["/api/papers/lookup"]["get"]
        param_names = [p["name"] for p in get_op.get("parameters", [])]
        assert "url" in param_names

    def test_url_parameter_is_required(self, client_with_papers):
        resp = client_with_papers.get("/openapi.json")
        schema = resp.json()

        get_op = schema["paths"]["/api/papers/lookup"]["get"]
        url_param = next(p for p in get_op["parameters"] if p["name"] == "url")
        assert url_param["required"] is True


# ---------------------------------------------------------------------------
# Auth: Lookup requires API key
# ---------------------------------------------------------------------------


class TestLookupAuth:
    """The lookup endpoint requires authentication."""

    def test_returns_401_without_api_key(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers/lookup",
            params={"url": "https://example.com/papers/cs101-midterm.pdf"},
        )
        assert resp.status_code == 401

    def test_returns_403_with_wrong_api_key(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers/lookup",
            params={"url": "https://example.com/papers/cs101-midterm.pdf"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 403
