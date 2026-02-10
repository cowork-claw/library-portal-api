import pytest


def test_get_papers_by_year_success(client, api_key_headers):
    metadata = client.get("/api/metadata", headers=api_key_headers).json()
    years = metadata["years"]
    assert years, "Expected at least one year in metadata"

    year = years[0]
    response = client.get(f"/api/papers/year/{year}", headers=api_key_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["total"] > 0
    assert len(data["papers"]) > 0
    assert all(p["year"] == year for p in data["papers"])


def test_get_papers_by_year_with_semester(client, api_key_headers):
    metadata = client.get("/api/metadata", headers=api_key_headers).json()
    years = metadata["years"]
    assert years, "Expected at least one year in metadata"

    year = None
    semester = None

    for candidate_year in years:
        year_resp = client.get(
            f"/api/papers/year/{candidate_year}", headers=api_key_headers
        )
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
        f"/api/papers/year/{year}?semester={semester}", headers=api_key_headers
    )
    assert response.status_code == 200

    data = response.json()
    assert data["total"] > 0
    assert all(p["year"] == year for p in data["papers"])
    assert all(p["semester"] == semester for p in data["papers"])


def test_get_papers_by_year_not_found(client, api_key_headers):
    metadata = client.get("/api/metadata", headers=api_key_headers).json()
    years = metadata["years"]
    assert years, "Expected at least one year in metadata"

    missing_year = min(years) - 1
    response = client.get(f"/api/papers/year/{missing_year}", headers=api_key_headers)
    assert response.status_code == 404


def test_get_papers_by_year_with_semester_empty_intersection(client, api_key_headers):
    metadata = client.get("/api/metadata", headers=api_key_headers).json()
    years = metadata["years"]
    all_semesters = set(metadata["semesters"])

    assert years, "Expected at least one year in metadata"
    assert all_semesters, "Expected at least one semester in metadata"

    for year in years:
        year_resp = client.get(f"/api/papers/year/{year}", headers=api_key_headers)
        assert year_resp.status_code == 200
        year_data = year_resp.json()

        year_semesters = {
            p.get("semester")
            for p in year_data["papers"]
            if p.get("semester") is not None
        }
        missing = sorted(s for s in all_semesters if s not in year_semesters)
        if not missing:
            continue

        missing_semester = missing[0]
        response = client.get(
            f"/api/papers/year/{year}?semester={missing_semester}",
            headers=api_key_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 0
        assert data["papers"] == []
        return

    pytest.skip("Could not find a (year, semester) combination with empty intersection")
