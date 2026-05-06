"""
Tests for the program_abbrev query parameter filter on GET /api/papers.

Covers validation contract assertions:
- VAL-USABILITY-001: filter returns only matching papers
- VAL-USABILITY-002: combines with other filters via intersection
- VAL-USABILITY-003: returns empty list when no match
- VAL-USABILITY-004: rejects values > 20 chars
- VAL-USABILITY-005: rejects empty/whitespace-only
- VAL-USABILITY-021: case-insensitive matching
- VAL-USABILITY-022: special characters handled safely
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
        "url": "http://example.com/u1",
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
        "url": "http://example.com/u2",
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
        "url": "http://example.com/u3",
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
    {
        "file_name": "me101-lab.pdf",
        "url": "http://example.com/u4",
        "year": 2023,
        "semester": 2,
        "course_code": "ME101",
        "course_name": "Thermodynamics",
        "degree_type": "B.Tech",
        "program_abbrev": "ME",
        "program": "B.Tech Mechanical",
        "streams": ["core"],
        "paper_type": "Regular",
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
# VAL-USABILITY-001: filter returns only matching papers
# ---------------------------------------------------------------------------


class TestProgramAbbrevFilterMatches:
    """program_abbrev filter returns only papers with matching abbreviation."""

    def test_filter_cse_returns_only_cse(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers", params={"program_abbrev": "CSE"}, headers=_auth_headers()
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        for paper in body["papers"]:
            assert paper["program_abbrev"] == "CSE"

    def test_filter_ece_returns_only_ece(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers", params={"program_abbrev": "ECE"}, headers=_auth_headers()
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["papers"][0]["program_abbrev"] == "ECE"

    def test_total_matches_papers_count(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers", params={"program_abbrev": "CSE"}, headers=_auth_headers()
        )
        body = resp.json()
        assert body["total"] == len(body["papers"])


# ---------------------------------------------------------------------------
# VAL-USABILITY-002: combines with other filters via intersection
# ---------------------------------------------------------------------------


class TestProgramAbbrevCombinesWithOtherFilters:
    """program_abbrev combines with year, semester, search via intersection."""

    def test_combine_with_year(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"program_abbrev": "CSE", "year": 2024},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        for paper in body["papers"]:
            assert paper["program_abbrev"] == "CSE"
            assert paper["year"] == 2024

    def test_combine_with_year_returns_empty_when_no_match(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"program_abbrev": "ECE", "year": 2024},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["papers"] == []

    def test_combine_with_semester(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"program_abbrev": "CSE", "semester": 1},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["papers"][0]["course_code"] == "CS101"

    def test_combine_with_course_code(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"program_abbrev": "CSE", "course_code": "CS201"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["papers"][0]["url"] == "http://example.com/u2"

    def test_combine_with_search(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"program_abbrev": "CSE", "search": "Algorithm"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["papers"][0]["course_name"] == "Algorithms"


# ---------------------------------------------------------------------------
# VAL-USABILITY-003: returns empty list when no match
# ---------------------------------------------------------------------------


class TestProgramAbbrevNoMatch:
    """Nonexistent abbreviation returns 200 with empty array."""

    def test_nonexistent_abbrev_returns_empty(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"program_abbrev": "XYZ"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["papers"] == []
        assert body["total"] == 0
        # Pagination metadata must be valid
        assert "pagination" in body
        assert body["pagination"]["total"] == 0


# ---------------------------------------------------------------------------
# VAL-USABILITY-004: rejects values > 20 chars
# ---------------------------------------------------------------------------


class TestProgramAbbrevMaxLength:
    """Values longer than 20 characters return 422."""

    def test_21_char_value_returns_422(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"program_abbrev": "A" * 21},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422
        detail = resp.json()
        # Error must reference program_abbrev
        locations = [e["loc"] for e in detail.get("detail", [])]
        assert any("program_abbrev" in str(loc) for loc in locations)

    def test_very_long_value_returns_422(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"program_abbrev": "X" * 100},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# VAL-USABILITY-005: rejects empty and whitespace-only
# ---------------------------------------------------------------------------


class TestProgramAbbrevEmptyAndWhitespace:
    """Empty or whitespace-only values return 422."""

    def test_empty_value_returns_422(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"program_abbrev": ""},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    def test_whitespace_only_returns_422(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"program_abbrev": "   "},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# VAL-USABILITY-021: case-insensitive matching
# ---------------------------------------------------------------------------


class TestProgramAbbrevCaseInsensitive:
    """program_abbrev=cse and program_abbrev=CSE return identical results."""

    def test_uppercase_and_lowercase_same_results(self, client_with_papers):
        resp_upper = client_with_papers.get(
            "/api/papers",
            params={"program_abbrev": "CSE"},
            headers=_auth_headers(),
        )
        resp_lower = client_with_papers.get(
            "/api/papers",
            params={"program_abbrev": "cse"},
            headers=_auth_headers(),
        )
        assert resp_upper.status_code == 200
        assert resp_lower.status_code == 200

        body_upper = resp_upper.json()
        body_lower = resp_lower.json()

        assert body_upper["total"] == body_lower["total"]
        assert body_upper["papers"] == body_lower["papers"]

    def test_mixed_case_same_results(self, client_with_papers):
        resp_mixed = client_with_papers.get(
            "/api/papers",
            params={"program_abbrev": "Cse"},
            headers=_auth_headers(),
        )
        resp_upper = client_with_papers.get(
            "/api/papers",
            params={"program_abbrev": "CSE"},
            headers=_auth_headers(),
        )
        assert resp_mixed.json()["total"] == resp_upper.json()["total"]


# ---------------------------------------------------------------------------
# VAL-USABILITY-022: special characters handled safely
# ---------------------------------------------------------------------------


class TestProgramAbbrevSpecialCharacters:
    """Injection-like strings are handled safely (no 500)."""

    @pytest.mark.parametrize(
        "value",
        [
            "'; DROP TABLE papers;--",
            "<script>alert('xss')</script>",
            "CSE\nECE",
            "../../../etc/passwd",
            "${jndi:ldap://evil}",
        ],
    )
    def test_special_strings_no_500(self, client_with_papers, value):
        resp = client_with_papers.get(
            "/api/papers",
            params={"program_abbrev": value},
            headers=_auth_headers(),
        )
        # Must be 200 (empty results) or 422, never 500
        assert resp.status_code in (
            200,
            422,
        ), f"Expected 200 or 422 for {value!r}, got {resp.status_code}"
        if resp.status_code == 200:
            body = resp.json()
            assert "papers" in body
