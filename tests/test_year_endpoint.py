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


def _headers() -> dict:
    return {"X-API-Key": "test-key"}


def test_get_papers_by_year_success(client):
    metadata = client.get("/api/metadata", headers=_headers()).json()
    years = metadata["years"]
    assert years, "Expected at least one year in metadata"

    year = years[0]
    response = client.get(f"/api/papers/year/{year}", headers=_headers())
    assert response.status_code == 200

    data = response.json()
    assert data["total"] > 0
    assert len(data["papers"]) > 0
    assert all(p["year"] == year for p in data["papers"])


def test_get_papers_by_year_with_semester(client):
    metadata = client.get("/api/metadata", headers=_headers()).json()
    years = metadata["years"]
    assert years, "Expected at least one year in metadata"

    year = None
    semester = None

    for candidate_year in years:
        year_resp = client.get(f"/api/papers/year/{candidate_year}", headers=_headers())
        assert year_resp.status_code == 200
        year_data = year_resp.json()
        if not year_data["papers"]:
            continue

        for p in year_data["papers"]:
            if p.get("semester") is not None:
                year = candidate_year
                semester = p["semester"]
                break

        if semester is not None:
            break

    if semester is None or year is None:
        pytest.skip("Could not find a paper with a non-null semester value")

    response = client.get(
        f"/api/papers/year/{year}?semester={semester}", headers=_headers()
    )
    assert response.status_code == 200

    data = response.json()
    assert data["total"] > 0
    assert all(p["year"] == year for p in data["papers"])
    assert all(p["semester"] == semester for p in data["papers"])


def test_get_papers_by_year_not_found(client):
    metadata = client.get("/api/metadata", headers=_headers()).json()
    years = metadata["years"]
    assert years, "Expected at least one year in metadata"

    missing_year = min(years) - 1
    response = client.get(f"/api/papers/year/{missing_year}", headers=_headers())
    assert response.status_code == 404


def test_get_papers_by_year_with_semester_empty_intersection(client):
    metadata = client.get("/api/metadata", headers=_headers()).json()
    years = metadata["years"]
    all_semesters = set(metadata["semesters"])

    assert years, "Expected at least one year in metadata"
    assert all_semesters, "Expected at least one semester in metadata"

    for year in years:
        year_resp = client.get(f"/api/papers/year/{year}", headers=_headers())
        assert year_resp.status_code == 200
        year_data = year_resp.json()

        year_semesters = {
            p.get("semester") for p in year_data["papers"] if p.get("semester") is not None
        }
        missing = sorted(s for s in all_semesters if s not in year_semesters)
        if not missing:
            continue

        missing_semester = missing[0]
        response = client.get(
            f"/api/papers/year/{year}?semester={missing_semester}", headers=_headers()
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 0
        assert data["papers"] == []
        return

    pytest.skip("Could not find a (year, semester) combination with empty intersection")

