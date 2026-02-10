from fastapi.testclient import TestClient
from app_v2.main import app

client = TestClient(app)


def test_search_query_too_long():
    """Test that search query longer than 100 characters returns 422."""
    long_query = "a" * 101
    response = client.get(f"/api/papers?search={long_query}")
    assert response.status_code == 422
    assert (
        "String should have at most 100 characters" in response.text
        or "less than or equal to 100" in response.text
    )


def test_search_query_valid_length():
    """Test that search query with 100 characters is accepted."""
    valid_query = "a" * 100
    response = client.get(f"/api/papers?search={valid_query}")
    # Should be 200 (or empty list if no results, but definitely not 422)
    assert response.status_code == 200


def test_year_validation_too_small():
    """Test that year < 2000 returns 422."""
    response = client.get("/api/papers?year=1999")
    assert response.status_code == 422


def test_year_validation_too_large():
    """Test that year > 2100 returns 422."""
    response = client.get("/api/papers?year=2101")
    assert response.status_code == 422


def test_year_validation_valid():
    """Test that valid year is accepted."""
    response = client.get("/api/papers?year=2024")
    assert response.status_code == 200


def test_year_path_validation_too_small():
    """Test that year path param < 2000 returns 422."""
    response = client.get("/api/papers/year/1999")
    assert response.status_code == 422


def test_year_path_validation_too_large():
    """Test that year path param > 2100 returns 422."""
    response = client.get("/api/papers/year/2101")
    assert response.status_code == 422


def test_semester_validation_too_small():
    """Test that semester < 1 returns 422."""
    response = client.get("/api/papers?semester=0")
    assert response.status_code == 422


def test_semester_validation_too_large():
    """Test that semester > 8 returns 422."""
    response = client.get("/api/papers?semester=9")
    assert response.status_code == 422


def test_semester_path_validation_too_small():
    """Test that semester path param < 1 returns 422."""
    response = client.get("/api/papers/semester/0")
    assert response.status_code == 422


def test_semester_path_validation_too_large():
    """Test that semester path param > 8 returns 422."""
    response = client.get("/api/papers/semester/9")
    assert response.status_code == 422
