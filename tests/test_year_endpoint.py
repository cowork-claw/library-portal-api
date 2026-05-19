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

    assert (
        semester is not None and year is not None
    ), "Expected at least one paper with a non-null semester value"

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

    assert years, "Expected at least one year in metadata"

    for year in years:
        populated = client.get(f"/api/papers/year/{year}", headers=api_key_headers)
        assert populated.status_code == 200
        if not populated.json()["total"]:
            continue

        for semester in range(1, 9):
            response = client.get(
                f"/api/papers/year/{year}?semester={semester}",
                headers=api_key_headers,
            )
            assert response.status_code == 200
            data = response.json()
            if data["total"] == 0:
                assert data["papers"] == []
                return

    assert False, "Expected at least one (year, semester) combination with no papers"
