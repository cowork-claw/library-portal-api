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

def test_get_papers_by_year_success(client):
    headers = {"X-API-Key": "test-key"}
    # 2022 is known to have data from previous steps
    response = client.get("/api/papers/year/2022", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    assert len(data["papers"]) > 0
    assert data["papers"][0]["year"] == 2022

def test_get_papers_by_year_with_semester(client):
    headers = {"X-API-Key": "test-key"}
    # 2022 sem 5 is known to have data
    response = client.get("/api/papers/year/2022?semester=5", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    for p in data["papers"]:
        assert p["year"] == 2022
        assert p["semester"] == 5

def test_get_papers_by_year_not_found(client):
    headers = {"X-API-Key": "test-key"}
    response = client.get("/api/papers/year/1900", headers=headers)
    assert response.status_code == 404

def test_get_papers_by_year_with_semester_empty_intersection(client):
    headers = {"X-API-Key": "test-key"}
    # Use a semester that likely has no intersection for that year but valid 1-8
    # We'll just verify the response structure is correct (empty list, 200 OK)
    response = client.get("/api/papers/year/2022?semester=8", headers=headers)
    assert response.status_code == 200
    data = response.json()
    # It might be empty or not, but strictly speaking if year exists, it shouldn't 404
    assert isinstance(data["papers"], list)
    assert isinstance(data["total"], int)
