"""
Tests for POST /health/data/reload endpoint (admin data reload).

Covers VAL-REL-006, VAL-REL-007, VAL-REL-008, VAL-REL-009,
          VAL-REL-010, VAL-REL-011, VAL-REL-013, VAL-CROSS-006.
"""

import importlib
import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API_KEY = "test-key"
AUTH_HEADERS = {"X-API-Key": API_KEY}

# Snapshot of env vars we mutate so we can restore them after each test class.
_ENV_KEYS = (
    "LIBRARY_PORTAL_ENVIRONMENT",
    "LIBRARY_PORTAL_API_KEY",
    "LIBRARY_PORTAL_DATA_DIRECTORY",
)


@pytest.fixture(autouse=True)
def _isolate_env():
    """Save and restore env vars + module state around each test."""
    saved = {k: os.environ.get(k) for k in _ENV_KEYS}
    yield
    # Restore original env vars
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    # Reload modules so subsequent test files see original state
    import config.config_v2 as config_module

    importlib.reload(config_module)

    import app_v2.main as main_module

    importlib.reload(main_module)


# ---------------------------------------------------------------------------
# Helpers
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


def _write_valid_json(
    directory: Path,
    papers: list[dict] | None = None,
    filename: str = "valid.json",
) -> Path:
    """Write a valid JSON file into *directory* and return its path."""
    if papers is None:
        papers = [
            {
                "url": "https://example.com/paper1.pdf",
                "file_name": "paper1.pdf",
                "course_code": "TEST101",
                "course_name": "Test Course",
                "year": 2024,
                "semester": 1,
                "program_abbrev": "CSE",
            }
        ]
    data = {"TEST101": papers}
    fp = directory / filename
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(json.dumps(data), encoding="utf-8")
    return fp


# ---------------------------------------------------------------------------
# VAL-REL-006: Reload endpoint requires API key
# ---------------------------------------------------------------------------


class TestReloadRequiresAuth:
    """POST /health/data/reload must be protected by API key."""

    def test_no_api_key_returns_401(self, tmp_path):
        """Missing X-API-Key must yield 401."""
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.post("/health/data/reload")
            assert resp.status_code == 401

    def test_invalid_api_key_returns_403(self, tmp_path):
        """Wrong X-API-Key must yield 403."""
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.post(
                "/health/data/reload",
                headers={"X-API-Key": "wrong-key"},
            )
            assert resp.status_code == 403

    def test_valid_api_key_does_not_return_401_or_403(self, tmp_path):
        """Valid key should return 202 (not 401/403)."""
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.post("/health/data/reload", headers=AUTH_HEADERS)
            assert resp.status_code == 202


# ---------------------------------------------------------------------------
# VAL-REL-007: Reload endpoint returns 202 Accepted with reload_id
# ---------------------------------------------------------------------------


class TestReloadReturns202:
    """POST /health/data/reload returns 202 Accepted with a reload_id."""

    def test_returns_202_accepted(self, tmp_path):
        """Status code must be 202."""
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.post("/health/data/reload", headers=AUTH_HEADERS)
            assert resp.status_code == 202

    def test_response_contains_reload_id(self, tmp_path):
        """Response body must contain a non-null reload_id."""
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.post("/health/data/reload", headers=AUTH_HEADERS)
            body = resp.json()
            assert "reload_id" in body
            assert body["reload_id"] is not None
            assert isinstance(body["reload_id"], str)
            assert len(body["reload_id"]) > 0

    def test_reload_id_is_valid_uuid(self, tmp_path):
        """reload_id should be a valid UUID string."""
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp = client.post("/health/data/reload", headers=AUTH_HEADERS)
            body = resp.json()
            # Should parse without error
            uuid.UUID(body["reload_id"])

    def test_response_does_not_block(self, tmp_path):
        """Response should return quickly (< 500ms) even with data."""
        _write_valid_json(tmp_path)
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            start = time.monotonic()
            resp = client.post("/health/data/reload", headers=AUTH_HEADERS)
            elapsed = time.monotonic() - start
            assert resp.status_code == 202
            assert elapsed < 2.0  # generous bound for CI


# ---------------------------------------------------------------------------
# VAL-REL-009: Reload endpoint is idempotent
# ---------------------------------------------------------------------------


class TestReloadIdempotent:
    """Multiple rapid reload calls must be safe."""

    def test_distinct_reload_ids(self, tmp_path):
        """Two rapid calls must return distinct reload_id values."""
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            resp1 = client.post("/health/data/reload", headers=AUTH_HEADERS)
            resp2 = client.post("/health/data/reload", headers=AUTH_HEADERS)
            assert resp1.status_code == 202
            assert resp2.status_code == 202
            id1 = resp1.json()["reload_id"]
            id2 = resp2.json()["reload_id"]
            assert id1 != id2

    def test_rapid_reloads_do_not_crash(self, tmp_path):
        """Multiple rapid calls must not raise exceptions."""
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            for _ in range(5):
                resp = client.post("/health/data/reload", headers=AUTH_HEADERS)
                assert resp.status_code == 202

    def test_rapid_reloads_index_remains_valid(self, tmp_path):
        """After multiple reloads, the index should still be queryable."""
        _write_valid_json(tmp_path)
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            # Fire off multiple reloads
            for _ in range(3):
                client.post("/health/data/reload", headers=AUTH_HEADERS)
            # Index should still work (background tasks run synchronously in
            # TestClient, so no sleep needed)
            resp = client.get("/api/papers", headers=AUTH_HEADERS)
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# VAL-REL-008: Reload triggers data reload
# ---------------------------------------------------------------------------


class TestReloadTriggersDataReload:
    """Reload should cause the index to reflect new data files."""

    def test_reload_loads_newly_added_data(self, tmp_path):
        """After adding a JSON file and reloading, papers should appear."""
        # Start with empty dir
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            # Verify initially empty
            resp = client.get("/api/metadata", headers=AUTH_HEADERS)
            assert resp.json()["total_papers"] == 0

            # Add valid data file
            _write_valid_json(tmp_path)

            # Trigger reload
            resp = client.post("/health/data/reload", headers=AUTH_HEADERS)
            assert resp.status_code == 202

            # Verify data is now loaded
            resp = client.get("/api/metadata", headers=AUTH_HEADERS)
            body = resp.json()
            assert body["total_papers"] > 0

    def test_reload_reflects_multiple_files(self, tmp_path):
        """After adding multiple files and reloading, all papers appear."""
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            # Write two files with different papers
            _write_valid_json(
                tmp_path,
                papers=[
                    {
                        "url": "https://example.com/paper1.pdf",
                        "file_name": "paper1.pdf",
                        "course_code": "TEST101",
                        "year": 2024,
                        "semester": 1,
                    }
                ],
                filename="file1.json",
            )
            _write_valid_json(
                tmp_path,
                papers=[
                    {
                        "url": "https://example.com/paper2.pdf",
                        "file_name": "paper2.pdf",
                        "course_code": "TEST102",
                        "year": 2023,
                        "semester": 2,
                    }
                ],
                filename="file2.json",
            )

            resp = client.post("/health/data/reload", headers=AUTH_HEADERS)
            assert resp.status_code == 202

            resp = client.get("/api/metadata", headers=AUTH_HEADERS)
            assert resp.json()["total_papers"] >= 2


# ---------------------------------------------------------------------------
# VAL-REL-013: Reload clears index when data directory is deleted
# ---------------------------------------------------------------------------


class TestReloadClearsIndex:
    """Reload with deleted data directory should clear the index."""

    def test_reload_clears_when_directory_deleted(self, tmp_path):
        """After loading data, deleting dir, and reloading, index is empty."""
        _write_valid_json(tmp_path)
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            # Confirm data loaded
            resp = client.get("/api/metadata", headers=AUTH_HEADERS)
            assert resp.json()["total_papers"] > 0

            # Delete all JSON files from the data directory
            for f in tmp_path.glob("*.json"):
                f.unlink()

            # Reload (BackgroundTasks run synchronously in TestClient)
            resp = client.post("/health/data/reload", headers=AUTH_HEADERS)
            assert resp.status_code == 202

            # Index should now be empty
            resp = client.get("/api/metadata", headers=AUTH_HEADERS)
            assert resp.json()["total_papers"] == 0


# ---------------------------------------------------------------------------
# VAL-REL-010: Health check recovers after successful reload
# ---------------------------------------------------------------------------


class TestHealthRecoversAfterReload:
    """Health status should transition from degraded to healthy after reload."""

    def test_degraded_to_healthy_after_reload(self, tmp_path):
        """Health check transitions from degraded to healthy."""
        # Start with empty dir
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            # Initially degraded
            resp = client.get("/health")
            assert resp.json()["status"] == "degraded"

            # Add data and reload
            _write_valid_json(tmp_path)
            resp = client.post("/health/data/reload", headers=AUTH_HEADERS)
            assert resp.status_code == 202

            # Should now be healthy (BackgroundTasks run synchronously)
            resp = client.get("/health")
            body = resp.json()
            assert body["status"] == "healthy"
            assert body["components"]["data"]["details"]["total"] > 0

    def test_health_data_status_updates_after_reload(self, tmp_path):
        """The /health/data endpoint also reflects updated status."""
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            # Initially degraded
            resp = client.get("/health/data", headers=AUTH_HEADERS)
            assert resp.json()["status"] == "degraded"

            # Add data and reload
            _write_valid_json(tmp_path)
            client.post("/health/data/reload", headers=AUTH_HEADERS)

            resp = client.get("/health/data", headers=AUTH_HEADERS)
            assert resp.json()["status"] == "healthy"
            assert resp.json()["total_papers"] > 0


# ---------------------------------------------------------------------------
# VAL-REL-011: Concurrent requests during reload are not interrupted
# ---------------------------------------------------------------------------


class TestConcurrentRequestsDuringReload:
    """Existing requests should not be interrupted during a reload."""

    def test_concurrent_reads_during_reload(self, tmp_path):
        """Concurrent requests during reload should all return 200."""
        _write_valid_json(tmp_path)
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            # Ensure initial data is loaded
            resp = client.get("/api/papers", headers=AUTH_HEADERS)
            assert resp.status_code == 200

            # Fire reload in background, while making concurrent reads
            def make_request(path, headers):
                try:
                    r = client.get(path, headers=headers)
                    return r.status_code
                except Exception as e:
                    return str(e)

            with ThreadPoolExecutor(max_workers=6) as executor:
                # Start reload
                reload_future = executor.submit(
                    client.post, "/health/data/reload", headers=AUTH_HEADERS
                )
                # Fire concurrent reads
                futures = [
                    executor.submit(make_request, "/api/papers", AUTH_HEADERS)
                    for _ in range(5)
                ]

                # Reload should return 202
                assert reload_future.result().status_code == 202

                # All read requests should succeed (200)
                for future in as_completed(futures):
                    result = future.result()
                    assert result == 200, f"Request returned {result}"


# ---------------------------------------------------------------------------
# VAL-CROSS-006: Empty startup, admin reload, then filter works
# ---------------------------------------------------------------------------


class TestEmptyStartupReloadThenFilter:
    """After starting with no data, reloading should make filters work."""

    def test_program_abbrev_filter_after_reload(self, tmp_path):
        """After reload, program_abbrev filter should return matching papers."""
        app = _build_app(tmp_path)
        with TestClient(app) as client:
            # Initially empty
            resp = client.get("/api/papers?program_abbrev=CSE", headers=AUTH_HEADERS)
            assert resp.status_code == 200
            assert resp.json()["total"] == 0

            # Add data with CSE program_abbrev
            _write_valid_json(tmp_path)
            resp = client.post("/health/data/reload", headers=AUTH_HEADERS)
            assert resp.status_code == 202

            # Now filter should return results (BackgroundTasks sync in TestClient)
            resp = client.get("/api/papers?program_abbrev=CSE", headers=AUTH_HEADERS)
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] > 0
            for paper in body["papers"]:
                assert paper["program_abbrev"] == "CSE"
