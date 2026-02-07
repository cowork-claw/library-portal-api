import importlib
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    os.environ["LIBRARY_PORTAL_ENVIRONMENT"] = "production"
    os.environ["LIBRARY_PORTAL_API_KEY"] = "test-key"

    import config.config_v2 as config_module

    importlib.reload(config_module)

    import app_v2.main as main_module

    importlib.reload(main_module)

    with TestClient(main_module.app) as test_client:
        yield test_client


def test_public_endpoints_require_no_api_key(client):
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_protected_endpoints_require_api_key(client):
    assert client.get("/api/metadata").status_code == 401
    assert client.get("/api/papers").status_code == 401
    assert client.get("/health/data").status_code == 401


def test_metadata_and_statistics_with_api_key(client):
    headers = {"X-API-Key": "test-key"}

    metadata_response = client.get("/api/metadata", headers=headers)
    assert metadata_response.status_code == 200
    metadata = metadata_response.json()
    assert metadata["total_papers"] > 0
    assert metadata["course_codes"]
    assert "program_abbrevs" in metadata

    stats_response = client.get("/api/statistics", headers=headers)
    assert stats_response.status_code == 200
    stats = stats_response.json()
    assert stats["total_papers"] == metadata["total_papers"]
    assert "papers_by_program_abbrev" in stats


def test_papers_pagination_and_course_endpoint(client):
    headers = {"X-API-Key": "test-key"}

    metadata = client.get("/api/metadata", headers=headers).json()
    course_code = metadata["course_codes"][0]

    papers_response = client.get("/api/papers?limit=1&offset=0", headers=headers)
    assert papers_response.status_code == 200
    papers_payload = papers_response.json()
    assert papers_payload["limit"] == 1
    assert papers_payload["total"] >= 1
    assert len(papers_payload["papers"]) <= 1
    assert "pagination" in papers_payload

    course_response = client.get(f"/api/papers/course/{course_code}", headers=headers)
    assert course_response.status_code == 200
    course_payload = course_response.json()
    assert course_payload["course_code"] == course_code.upper()
    assert course_payload["total_papers"] >= 1


def test_papers_search_query_returns_payload(client):
    headers = {"X-API-Key": "test-key"}

    # We don't assert exact search hits (data-dependent), just that the endpoint
    # accepts the query and returns the standard payload structure.
    response = client.get("/api/papers?limit=2&offset=0&search=zzz", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["limit"] == 2
    assert "total" in payload
    assert isinstance(payload["papers"], list)
    assert "pagination" in payload
