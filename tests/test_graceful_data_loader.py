"""
Tests for graceful data loader degradation.

Covers VAL-REL-001, VAL-REL-002, VAL-REL-003, VAL-REL-004, VAL-REL-005, VAL-REL-012.
"""

import importlib
import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API_KEY = "test-key"
AUTH_HEADERS = {"X-API-Key": API_KEY}


# ---------------------------------------------------------------------------
# Helpers – build a client whose DATA_DIRECTORY points at a temp directory
# ---------------------------------------------------------------------------


def _build_app(data_dir: Path):
    """Reload config/main modules and return a FastAPI app pointed at *data_dir*."""
    os.environ["LIBRARY_PORTAL_ENVIRONMENT"] = "production"
    os.environ["LIBRARY_PORTAL_API_KEY"] = API_KEY
    os.environ["LIBRARY_PORTAL_DATA_DIRECTORY"] = str(data_dir)

    import config.config_v2 as config_module

    importlib.reload(config_module)

    import app_v2.main as main_module

    importlib.reload(main_module)

    return main_module.app


def _write_valid_json(directory: Path, papers: list[dict] | None = None) -> Path:
    """Write a valid JSON file into *directory* and return its path."""
    if papers is None:
        papers = [
            {
                "url": "https://example.com/paper1.pdf",
                "file_name": "paper1.pdf",
                "course_code": "TEST101",
                "year": 2024,
                "semester": 1,
            }
        ]
    data = {"TEST101": papers}
    fp = directory / "valid.json"
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(json.dumps(data), encoding="utf-8")
    return fp


def _write_corrupt_json(directory: Path, name: str = "corrupt.json") -> Path:
    fp = directory / name
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text("{not valid json", encoding="utf-8")
    return fp


# ---------------------------------------------------------------------------
# VAL-REL-001: API starts when data directory is missing
# ---------------------------------------------------------------------------


class TestMissingDataDirectory:
    """VAL-REL-001: API starts successfully when DATA_DIRECTORY is missing."""

    def test_api_starts_with_missing_directory(self, tmp_path):
        """API should start even when DATA_DIRECTORY does not exist."""
        nonexistent = tmp_path / "does_not_exist"
        app = _build_app(nonexistent)
        with TestClient(app) as client:
            resp = client.get("/health")
            assert resp.status_code == 200

    def test_health_returns_degraded_when_directory_missing(self, tmp_path):
        """Health check should report 'degraded' when data dir is missing."""
        nonexistent = tmp_path / "does_not_exist"
        app = _build_app(nonexistent)
        with TestClient(app) as client:
            resp = client.get("/health")
            data = resp.json()
            assert data["status"] == "degraded"
            assert data["components"]["data"]["status"] == "degraded"
            assert data["components"]["data"]["details"]["total"] == 0

    def test_loader_stats_no_absolute_paths_missing_dir(self, tmp_path):
        """Error messages must not contain absolute filesystem paths."""
        nonexistent = tmp_path / "does_not_exist"
        app = _build_app(nonexistent)
        with TestClient(app) as client:
            resp = client.get("/health/data", headers=AUTH_HEADERS)
            assert resp.status_code == 200
            body = resp.json()
            for err in body.get("errors", []):
                assert not err.startswith("/"), f"Error message leaks path: {err}"


# ---------------------------------------------------------------------------
# VAL-REL-002: API starts when all JSON files are corrupt
# ---------------------------------------------------------------------------


class TestAllCorruptFiles:
    """VAL-REL-002: API starts when all JSON files are invalid."""

    def test_api_starts_with_all_corrupt_files(self, tmp_path):
        """API should start even when every JSON file is corrupt."""
        _write_corrupt_json(tmp_path, "bad1.json")
        _write_corrupt_json(tmp_path, "bad2.json")
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.get("/health")
            assert resp.status_code == 200

    def test_zero_papers_with_all_corrupt(self, tmp_path):
        """Zero papers should be loaded when all files are corrupt."""
        _write_corrupt_json(tmp_path, "bad1.json")
        _write_corrupt_json(tmp_path, "bad2.json")
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.get("/health")
            data = resp.json()
            assert data["components"]["data"]["details"]["total"] == 0
            assert data["components"]["data"]["status"] == "degraded"

    def test_corrupt_file_errors_recorded_without_paths(self, tmp_path):
        """Errors from corrupt files must be recorded but without absolute paths."""
        _write_corrupt_json(tmp_path, "bad1.json")
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.get("/health/data", headers=AUTH_HEADERS)
            assert resp.status_code == 200
            body = resp.json()
            assert len(body["errors"]) > 0
            for err in body["errors"]:
                assert str(tmp_path) not in err, f"Error leaks path: {err}"


# ---------------------------------------------------------------------------
# VAL-REL-003: Health check reports 'degraded' when no data
# ---------------------------------------------------------------------------


class TestDegradedHealthStatus:
    """VAL-REL-003: Health check reports 'degraded' (not 'unhealthy')."""

    def test_health_degraded_when_no_papers(self, tmp_path):
        """Overall health should be 'degraded' when total_papers == 0."""
        # Empty dir (no JSON files)
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.get("/health")
            data = resp.json()
            assert data["status"] == "degraded"
            assert data["components"]["data"]["status"] == "degraded"

    def test_health_data_degraded_when_no_papers(self, tmp_path):
        """/health/data should report 'degraded' when total_papers == 0."""
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.get("/health/data", headers=AUTH_HEADERS)
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "degraded"
            assert body["total_papers"] == 0

    def test_health_changes_to_healthy_after_data_loaded(self, tmp_path):
        """Health should be 'healthy' when papers are present."""
        _write_valid_json(tmp_path)
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.get("/health")
            data = resp.json()
            assert data["status"] == "healthy"
            assert data["components"]["data"]["status"] == "healthy"
            assert data["components"]["data"]["details"]["total"] > 0


# ---------------------------------------------------------------------------
# VAL-REL-004: Papers endpoints return empty list without data
# ---------------------------------------------------------------------------


class TestEmptyPapersEndpoints:
    """VAL-REL-004: Papers endpoints return 200 with empty papers when index is empty."""

    def test_papers_list_empty(self, tmp_path):
        """GET /api/papers should return 200 with empty papers array."""
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.get("/api/papers", headers=AUTH_HEADERS)
            assert resp.status_code == 200
            body = resp.json()
            assert body["papers"] == []
            assert body["total"] == 0
            assert body["pagination"]["total"] == 0

    def test_papers_search_empty(self, tmp_path):
        """GET /api/papers?search=... should return 200 with empty results."""
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.get("/api/papers?search=cs", headers=AUTH_HEADERS)
            assert resp.status_code == 200
            body = resp.json()
            assert body["papers"] == []
            assert body["total"] == 0

    def test_papers_by_year_not_found(self, tmp_path):
        """GET /api/papers/year/2024 should return 404 when no data."""
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.get("/api/papers/year/2024", headers=AUTH_HEADERS)
            assert resp.status_code == 404

    def test_papers_pagination_valid_when_empty(self, tmp_path):
        """Pagination metadata should be valid even with empty data."""
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.get("/api/papers?limit=10&offset=0", headers=AUTH_HEADERS)
            assert resp.status_code == 200
            body = resp.json()
            pagination = body["pagination"]
            assert pagination["total"] == 0
            assert pagination["has_next"] is False
            assert pagination["has_prev"] is False


# ---------------------------------------------------------------------------
# VAL-REL-005: Metadata endpoints return empty collections without data
# ---------------------------------------------------------------------------


class TestEmptyMetadataEndpoints:
    """VAL-REL-005: Metadata endpoints return 200 with empty collections."""

    def test_metadata_empty(self, tmp_path):
        """GET /api/metadata should return 200 with empty lists and total_papers=0."""
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.get("/api/metadata", headers=AUTH_HEADERS)
            assert resp.status_code == 200
            body = resp.json()
            assert body["total_papers"] == 0
            assert body["years"] == []
            assert body["programs"] == []
            assert body["program_abbrevs"] == []
            assert body["semesters"] == []
            assert body["paper_types"] == []
            assert body["degree_types"] == []
            assert body["course_codes"] == []
            assert body["streams"] == []

    def test_statistics_empty(self, tmp_path):
        """GET /api/statistics should return 200 with empty counts."""
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.get("/api/statistics", headers=AUTH_HEADERS)
            assert resp.status_code == 200
            body = resp.json()
            assert body["total_papers"] == 0
            assert body["courses_count"] == 0
            assert body["files_loaded"] == 0
            assert dict(body["papers_by_year"]) == {}
            assert dict(body["papers_by_semester"]) == {}


# ---------------------------------------------------------------------------
# VAL-REL-012: API starts with partial data corruption
# ---------------------------------------------------------------------------


class TestPartialCorruption:
    """VAL-REL-012: API starts with mix of valid and corrupt files."""

    def test_api_starts_with_mixed_files(self, tmp_path):
        """API should load valid files and skip corrupt ones."""
        _write_valid_json(tmp_path)
        _write_corrupt_json(tmp_path, "bad.json")
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "healthy"
            assert data["components"]["data"]["details"]["total"] > 0

    def test_partial_corruption_records_errors(self, tmp_path):
        """Errors should be recorded for corrupt files when valid ones also exist."""
        _write_valid_json(tmp_path)
        _write_corrupt_json(tmp_path, "bad.json")
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.get("/health/data", headers=AUTH_HEADERS)
            assert resp.status_code == 200
            body = resp.json()
            assert len(body["errors"]) > 0
            assert body["total_papers"] > 0

    def test_partial_corruption_no_path_leak(self, tmp_path):
        """Error messages should not contain absolute paths even in partial corruption."""
        _write_valid_json(tmp_path)
        _write_corrupt_json(tmp_path, "bad.json")
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.get("/health/data", headers=AUTH_HEADERS)
            assert resp.status_code == 200
            body = resp.json()
            for err in body["errors"]:
                assert str(tmp_path) not in err, f"Error leaks path: {err}"

    def test_valid_papers_searchable_with_corrupt_files(self, tmp_path):
        """Valid papers should be searchable even when corrupt files exist."""
        _write_valid_json(tmp_path)
        _write_corrupt_json(tmp_path, "bad.json")
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.get("/api/papers", headers=AUTH_HEADERS)
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] > 0
            assert len(body["papers"]) > 0


# ---------------------------------------------------------------------------
# DataLoader unit tests (direct, no HTTP)
# ---------------------------------------------------------------------------


class TestDataLoaderUnit:
    """Unit tests for DataLoader class."""

    def test_missing_directory_returns_empty(self, tmp_path):
        """DataLoader.load_all() should return [] when directory doesn't exist."""
        from app_v2.data_loader import DataLoader

        loader = DataLoader(tmp_path / "nonexistent")
        result = loader.load_all()
        assert result == []
        assert loader.stats.errors
        # Error should not contain absolute path
        for err in loader.stats.errors:
            assert str(tmp_path) not in err

    def test_empty_directory_returns_empty(self, tmp_path):
        """DataLoader.load_all() should return [] when directory is empty."""
        from app_v2.data_loader import DataLoader

        loader = DataLoader(tmp_path)
        result = loader.load_all()
        assert result == []

    def test_corrupt_file_records_error(self, tmp_path):
        """Corrupt JSON should be recorded in errors but not crash."""
        from app_v2.data_loader import DataLoader

        _write_corrupt_json(tmp_path)
        loader = DataLoader(tmp_path)
        result = loader.load_all()
        assert result == []
        assert len(loader.stats.errors) == 1
        assert "corrupt.json" in loader.stats.errors[0]

    def test_valid_file_loads_papers(self, tmp_path):
        """Valid JSON should load papers correctly."""
        from app_v2.data_loader import DataLoader

        _write_valid_json(tmp_path)
        loader = DataLoader(tmp_path)
        result = loader.load_all()
        assert len(result) == 1
        assert result[0]["url"] == "https://example.com/paper1.pdf"

    def test_mixed_valid_and_corrupt(self, tmp_path):
        """Valid files should load; corrupt files should be skipped with errors."""
        from app_v2.data_loader import DataLoader

        _write_valid_json(tmp_path)
        _write_corrupt_json(tmp_path)
        loader = DataLoader(tmp_path)
        result = loader.load_all()
        assert len(result) == 1
        assert len(loader.stats.errors) == 1

    def test_error_messages_no_absolute_paths(self, tmp_path):
        """No error message should contain absolute filesystem paths."""
        from app_v2.data_loader import DataLoader

        _write_corrupt_json(tmp_path, "bad.json")
        loader = DataLoader(tmp_path)
        loader.load_all()
        for err in loader.stats.errors:
            # Check that absolute path is not present
            assert str(tmp_path) not in err, f"Error leaks absolute path: {err}"
            # Error should only reference filename
            assert "bad.json" in err
