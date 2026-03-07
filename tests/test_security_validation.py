import importlib
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    # Set environment to production to ensure API key enforcement
    os.environ["LIBRARY_PORTAL_ENVIRONMENT"] = "production"
    os.environ["LIBRARY_PORTAL_API_KEY"] = "test-key"

    import config.config_v2 as config_module

    importlib.reload(config_module)

    import app_v2.main as main_module

    importlib.reload(main_module)

    with TestClient(main_module.app) as test_client:
        yield test_client


def _headers() -> dict:
    return {"X-API-Key": "test-key"}


def test_search_query_too_long(client):
    """Test that search query longer than 100 characters returns 422."""
    long_query = "a" * 101
    response = client.get(f"/api/papers?search={long_query}", headers=_headers())
    assert response.status_code == 422
    detail = response.json().get("detail", [])
    # Avoid brittle, version-specific pydantic error strings; just verify it's a
    # validation error on the `search` field.
    assert any("search" in map(str, item.get("loc", [])) for item in detail)


def test_search_query_valid_length(client, monkeypatch):
    """Test that search query with 100 characters is accepted."""
    # Keep this test focused on parameter validation. Fuzzy search over the full
    # dataset can be slow/data-dependent, so stub it to a fast no-op.
    import app_v2.routes.papers as papers_routes

    # Mock paper_index.search instead of search_papers
    monkeypatch.setattr(papers_routes.paper_index, "search", lambda q: [])

    valid_query = "a" * 100
    response = client.get(f"/api/papers?search={valid_query}", headers=_headers())
    # Should be 200 (or empty list if no results, but definitely not 422)
    assert response.status_code == 200


def test_year_validation_too_small(client):
    """Test that year < 2000 returns 422."""
    response = client.get("/api/papers?year=1999", headers=_headers())
    assert response.status_code == 422


def test_year_validation_too_large(client):
    """Test that year > 2100 returns 422."""
    response = client.get("/api/papers?year=2101", headers=_headers())
    assert response.status_code == 422


def test_year_validation_valid(client):
    """Test that valid year is accepted."""
    response = client.get("/api/papers?year=2024", headers=_headers())
    assert response.status_code == 200


def test_year_path_validation_too_small(client):
    """Test that year path param < 2000 returns 422."""
    response = client.get("/api/papers/year/1999", headers=_headers())
    assert response.status_code == 422


def test_year_path_validation_too_large(client):
    """Test that year path param > 2100 returns 422."""
    response = client.get("/api/papers/year/2101", headers=_headers())
    assert response.status_code == 422


def test_semester_validation_too_small(client):
    """Test that semester < 1 returns 422."""
    response = client.get("/api/papers?semester=0", headers=_headers())
    assert response.status_code == 422


def test_semester_validation_too_large(client):
    """Test that semester > 8 returns 422."""
    response = client.get("/api/papers?semester=9", headers=_headers())
    assert response.status_code == 422


def test_semester_path_validation_too_small(client):
    """Test that semester path param < 1 returns 422."""
    response = client.get("/api/papers/semester/0", headers=_headers())
    assert response.status_code == 422


def test_semester_path_validation_too_large(client):
    """Test that semester path param > 8 returns 422."""
    response = client.get("/api/papers/semester/9", headers=_headers())
    assert response.status_code == 422


def test_program_length_validation(client):
    """Test that program filter exceeding max length returns 422."""
    long_program = "a" * 51
    response = client.get(f"/api/papers?program={long_program}", headers=_headers())
    assert response.status_code == 422


def test_course_code_length_validation(client):
    """Test that course_code filter exceeding max length returns 422."""
    long_code = "a" * 21
    response = client.get(f"/api/papers?course_code={long_code}", headers=_headers())
    assert response.status_code == 422
