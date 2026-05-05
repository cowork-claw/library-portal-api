"""
Tests for sort and order query parameters on GET /api/papers.

Covers validation contract assertions:
- VAL-USABILITY-006: Sort by year ascending
- VAL-USABILITY-007: Sort by year descending
- VAL-USABILITY-008: Sort by semester ascending
- VAL-USABILITY-009: Sort by semester descending
- VAL-USABILITY-010: Sort by relevance when search is provided
- VAL-USABILITY-011: Default sort behavior (no sort param)
- VAL-USABILITY-012: Sort parameter rejects invalid sort fields
- VAL-USABILITY-013: Sort parameter rejects invalid order values
- VAL-USABILITY-019: Pagination is consistent across sort orders
- VAL-USABILITY-020: Relevance sort without search defaults safely
- VAL-USABILITY-023: Default order when only sort is provided
- VAL-CROSS-001: program_abbrev filter combined with sort by year desc
- VAL-CROSS-002: Search combined with program_abbrev filter and sort by relevance
- VAL-CROSS-009: Sort parameter works correctly on empty data
"""

import json

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_PAPERS = [
    {
        "file_name": "cs101-2024-s1.pdf",
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
        "file_name": "cs201-2024-s2.pdf",
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
        "file_name": "ee101-2023-s1.pdf",
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
        "file_name": "me101-2023-s2.pdf",
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
    {
        "file_name": "cs301-2022-s3.pdf",
        "url": "http://example.com/u5",
        "year": 2022,
        "semester": 3,
        "course_code": "CS301",
        "course_name": "Operating Systems",
        "degree_type": "B.Tech",
        "program_abbrev": "CSE",
        "program": "B.Tech Computer Science",
        "streams": ["cs"],
        "paper_type": "Regular",
    },
    # Paper with null year and null semester for nulls-last testing
    {
        "file_name": "xx000-null.pdf",
        "url": "http://example.com/u6",
        "year": None,
        "semester": None,
        "course_code": "XX000",
        "course_name": "Unknown Subject",
        "degree_type": "B.Tech",
        "program_abbrev": "CSE",
        "program": "B.Tech Computer Science",
        "streams": ["cs"],
        "paper_type": "Regular",
    },
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client_with_papers(tmp_path, monkeypatch):
    """Create a TestClient with sample papers loaded from a temp directory."""
    import importlib
    import os

    import config.config_v2 as config_module

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


@pytest.fixture()
def client_empty(tmp_path, monkeypatch):
    """Create a TestClient with no papers (empty data directory)."""
    import importlib
    import os

    import config.config_v2 as config_module

    data_dir = tmp_path / "organized"
    data_dir.mkdir()
    data_file = data_dir / "papers.json"
    data_file.write_text("{}")

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
# VAL-USABILITY-006: Sort by year ascending
# ---------------------------------------------------------------------------


class TestSortByYearAsc:
    """sort=year&order=asc returns papers ordered by year ascending, nulls last."""

    def test_year_values_monotonically_non_decreasing(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"sort": "year", "order": "asc"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        years = [p["year"] for p in body["papers"]]
        # Separate non-null and null values
        non_null = [y for y in years if y is not None]
        null_count = years.count(None)

        # Non-null values should be monotonically non-decreasing
        for i in range(1, len(non_null)):
            assert non_null[i] >= non_null[i - 1], (
                f"Years not ascending: {non_null}"
            )

        # Nulls should appear after all non-null values
        if null_count > 0:
            assert None not in years[: len(non_null)], "Null year appeared before non-null"

    def test_at_least_two_distinct_years(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"sort": "year", "order": "asc", "limit": 100},
            headers=_auth_headers(),
        )
        body = resp.json()
        years = set(p["year"] for p in body["papers"] if p["year"] is not None)
        assert len(years) >= 2


# ---------------------------------------------------------------------------
# VAL-USABILITY-007: Sort by year descending
# ---------------------------------------------------------------------------


class TestSortByYearDesc:
    """sort=year&order=desc returns papers ordered by year descending, nulls last."""

    def test_year_values_monotonically_non_increasing(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"sort": "year", "order": "desc"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        years = [p["year"] for p in body["papers"]]
        non_null = [y for y in years if y is not None]
        null_count = years.count(None)

        for i in range(1, len(non_null)):
            assert non_null[i] <= non_null[i - 1], (
                f"Years not descending: {non_null}"
            )

        if null_count > 0:
            assert None not in years[: len(non_null)], "Null year appeared before non-null"


# ---------------------------------------------------------------------------
# VAL-USABILITY-008: Sort by semester ascending
# ---------------------------------------------------------------------------


class TestSortBySemesterAsc:
    """sort=semester&order=asc returns papers ordered by semester ascending, nulls last."""

    def test_semester_values_monotonically_non_decreasing(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"sort": "semester", "order": "asc"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        semesters = [p["semester"] for p in body["papers"]]
        non_null = [s for s in semesters if s is not None]
        null_count = semesters.count(None)

        for i in range(1, len(non_null)):
            assert non_null[i] >= non_null[i - 1], (
                f"Semesters not ascending: {non_null}"
            )

        if null_count > 0:
            assert None not in semesters[: len(non_null)]


# ---------------------------------------------------------------------------
# VAL-USABILITY-009: Sort by semester descending
# ---------------------------------------------------------------------------


class TestSortBySemesterDesc:
    """sort=semester&order=desc returns papers ordered by semester descending, nulls last."""

    def test_semester_values_monotonically_non_increasing(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"sort": "semester", "order": "desc"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        semesters = [p["semester"] for p in body["papers"]]
        non_null = [s for s in semesters if s is not None]
        null_count = semesters.count(None)

        for i in range(1, len(non_null)):
            assert non_null[i] <= non_null[i - 1], (
                f"Semesters not descending: {non_null}"
            )

        if null_count > 0:
            assert None not in semesters[: len(non_null)]


# ---------------------------------------------------------------------------
# VAL-USABILITY-010: Sort by relevance when search is provided
# ---------------------------------------------------------------------------


class TestSortByRelevance:
    """sort=relevance with search query orders by search relevance."""

    def test_relevance_order_with_search(self, client_with_papers):
        """Papers are ordered by search relevance (best match first)."""
        resp = client_with_papers.get(
            "/api/papers",
            params={"search": "Algorithm", "sort": "relevance"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        # The "Algorithms" course should be the top result
        assert "Algorithms" in body["papers"][0].get("course_name", "")


# ---------------------------------------------------------------------------
# VAL-USABILITY-011: Default sort behavior (no sort param)
# ---------------------------------------------------------------------------


class TestDefaultSortBehavior:
    """Default sort: relevance if search present, year desc otherwise."""

    def test_default_with_search_is_relevance(self, client_with_papers):
        """When search is provided without sort, results are ordered by relevance."""
        resp = client_with_papers.get(
            "/api/papers",
            params={"search": "Algorithm"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        # Top result should be the best match (Algorithms course)
        assert "Algorithms" in body["papers"][0].get("course_name", "")

    def test_default_without_search_is_year_desc(self, client_with_papers):
        """When no search and no sort, results are ordered by year descending."""
        resp = client_with_papers.get(
            "/api/papers",
            params={"limit": 100},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        years = [p["year"] for p in body["papers"] if p["year"] is not None]
        for i in range(1, len(years)):
            assert years[i] <= years[i - 1], (
                f"Default order not year desc: {years}"
            )


# ---------------------------------------------------------------------------
# VAL-USABILITY-012: Sort parameter rejects invalid sort fields
# ---------------------------------------------------------------------------


class TestInvalidSortFields:
    """Invalid sort field values return 422."""

    @pytest.mark.parametrize("invalid_sort", ["name", "invalid", "date", "title", "YEAR", "Year"])
    def test_invalid_sort_returns_422(self, client_with_papers, invalid_sort):
        resp = client_with_papers.get(
            "/api/papers",
            params={"sort": invalid_sort},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422, (
            f"Expected 422 for sort={invalid_sort!r}, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# VAL-USABILITY-013: Sort parameter rejects invalid order values
# ---------------------------------------------------------------------------


class TestInvalidOrderValues:
    """Invalid order values return 422."""

    @pytest.mark.parametrize("invalid_order", ["ascending", "descending", "up", "down", "DESC", "Asc"])
    def test_invalid_order_returns_422(self, client_with_papers, invalid_order):
        resp = client_with_papers.get(
            "/api/papers",
            params={"sort": "year", "order": invalid_order},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422, (
            f"Expected 422 for order={invalid_order!r}, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# VAL-USABILITY-019: Pagination is consistent across sort orders
# ---------------------------------------------------------------------------


class TestPaginationConsistency:
    """Pagination is deterministic and stable across sort orders."""

    def test_second_page_continues_sorted_sequence(self, client_with_papers):
        """Page 2 of year-desc results continues from page 1 without overlap."""
        # Get all results for comparison
        resp_all = client_with_papers.get(
            "/api/papers",
            params={"sort": "year", "order": "desc", "limit": 100},
            headers=_auth_headers(),
        )
        all_papers = resp_all.json()["papers"]

        # Get page 1 (limit=3, offset=0)
        resp_p1 = client_with_papers.get(
            "/api/papers",
            params={"sort": "year", "order": "desc", "limit": 3, "offset": 0},
            headers=_auth_headers(),
        )
        page1_urls = [p["url"] for p in resp_p1.json()["papers"]]

        # Get page 2 (limit=3, offset=3)
        resp_p2 = client_with_papers.get(
            "/api/papers",
            params={"sort": "year", "order": "desc", "limit": 3, "offset": 3},
            headers=_auth_headers(),
        )
        page2_urls = [p["url"] for p in resp_p2.json()["papers"]]

        # No overlap
        assert set(page1_urls).isdisjoint(set(page2_urls)), (
            f"Pages overlap: {page1_urls} vs {page2_urls}"
        )

        # Page 2 URLs match the 4th-6th papers in the full sorted list
        expected_page2_urls = [p["url"] for p in all_papers[3:6]]
        assert page2_urls == expected_page2_urls

    def test_same_query_returns_identical_results(self, client_with_papers):
        """Repeating the same sorted query yields identical results."""
        params = {"sort": "year", "order": "desc", "limit": 5, "offset": 0}
        resp1 = client_with_papers.get("/api/papers", params=params, headers=_auth_headers())
        resp2 = client_with_papers.get("/api/papers", params=params, headers=_auth_headers())

        urls1 = [p["url"] for p in resp1.json()["papers"]]
        urls2 = [p["url"] for p in resp2.json()["papers"]]
        assert urls1 == urls2


# ---------------------------------------------------------------------------
# VAL-USABILITY-020: Relevance sort without search defaults safely
# ---------------------------------------------------------------------------


class TestRelevanceSortWithoutSearch:
    """sort=relevance without search falls back to year descending."""

    def test_relevance_without_search_returns_200(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"sort": "relevance"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] > 0

    def test_relevance_without_search_uses_year_desc_fallback(self, client_with_papers):
        """When sort=relevance without search, results are ordered by year desc."""
        resp = client_with_papers.get(
            "/api/papers",
            params={"sort": "relevance", "limit": 100},
            headers=_auth_headers(),
        )
        body = resp.json()
        years = [p["year"] for p in body["papers"] if p["year"] is not None]
        for i in range(1, len(years)):
            assert years[i] <= years[i - 1], (
                f"Relevance fallback not year desc: {years}"
            )


# ---------------------------------------------------------------------------
# VAL-USABILITY-023: Default order when only sort is provided
# ---------------------------------------------------------------------------


class TestDefaultOrderWhenOnlySortProvided:
    """When sort=year is given without order, default to desc."""

    def test_sort_year_without_order_defaults_to_desc(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"sort": "year"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        years = [p["year"] for p in body["papers"] if p["year"] is not None]
        for i in range(1, len(years)):
            assert years[i] <= years[i - 1], (
                f"Default order not desc: {years}"
            )

    def test_sort_semester_without_order_defaults_to_desc(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"sort": "semester"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        semesters = [p["semester"] for p in body["papers"] if p["semester"] is not None]
        for i in range(1, len(semesters)):
            assert semesters[i] <= semesters[i - 1], (
                f"Default order not desc: {semesters}"
            )


# ---------------------------------------------------------------------------
# VAL-CROSS-001: program_abbrev filter combined with sort by year desc
# ---------------------------------------------------------------------------


class TestProgramAbbrevWithSort:
    """program_abbrev=CSE&sort=year&order=desc returns only CSE papers sorted by year desc."""

    def test_filter_and_sort_combined(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"program_abbrev": "CSE", "sort": "year", "order": "desc"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        # All papers must be CSE
        for paper in body["papers"]:
            assert paper["program_abbrev"] == "CSE"
        # Year values must be descending (non-null)
        years = [p["year"] for p in body["papers"] if p["year"] is not None]
        for i in range(1, len(years)):
            assert years[i] <= years[i - 1]
        # Pagination fields present
        assert "pagination" in body

    def test_filter_with_sort_asc(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={"program_abbrev": "CSE", "sort": "year", "order": "asc"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        for paper in body["papers"]:
            assert paper["program_abbrev"] == "CSE"
        years = [p["year"] for p in body["papers"] if p["year"] is not None]
        for i in range(1, len(years)):
            assert years[i] >= years[i - 1]


# ---------------------------------------------------------------------------
# VAL-CROSS-002: Search + program_abbrev + sort by relevance
# ---------------------------------------------------------------------------


class TestSearchWithFilterAndRelevanceSort:
    """search + program_abbrev + sort=relevance returns intersection sorted by relevance."""

    def test_search_and_filter_relevance(self, client_with_papers):
        resp = client_with_papers.get(
            "/api/papers",
            params={
                "search": "Algorithm",
                "program_abbrev": "CSE",
                "sort": "relevance",
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        # All papers must be CSE
        for paper in body["papers"]:
            assert paper["program_abbrev"] == "CSE"
        # Must have at least one result (Algorithms is CSE)
        assert body["total"] >= 1
        # Top result should match the search
        assert "Algorithms" in body["papers"][0].get("course_name", "")

    def test_search_and_filter_excludes_non_matching(self, client_with_papers):
        """Search for 'Circuits' + program_abbrev=CSE returns empty (Circuits is ECE)."""
        resp = client_with_papers.get(
            "/api/papers",
            params={
                "search": "Circuits",
                "program_abbrev": "CSE",
                "sort": "relevance",
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["papers"] == []


# ---------------------------------------------------------------------------
# VAL-CROSS-009: Sort parameter works correctly on empty data
# ---------------------------------------------------------------------------


class TestSortOnEmptyData:
    """Sort works on empty index without errors."""

    @pytest.mark.parametrize(
        "sort,order",
        [
            ("year", "asc"),
            ("year", "desc"),
            ("semester", "asc"),
            ("semester", "desc"),
            ("relevance", "asc"),
            ("relevance", "desc"),
        ],
    )
    def test_empty_index_sort_returns_200(self, client_empty, sort, order):
        resp = client_empty.get(
            "/api/papers",
            params={"sort": sort, "order": order},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["papers"] == []
        assert body["total"] == 0
        assert "pagination" in body

    def test_empty_index_default_sort(self, client_empty):
        """Default sort on empty index returns valid response."""
        resp = client_empty.get(
            "/api/papers",
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["papers"] == []
        assert body["total"] == 0
