from app_v2.services.search import search_papers


def _sample_papers():
    return [
        {
            "file_name": "cs101-midterm.pdf",
            "course_code": "CS101",
            "course_name": "Introduction to Computer Science",
            "subject_name": "Programming",
            "display_title": "CS101 Midterm",
            "url": "u1",
        },
        {
            "file_name": "ma201-final.pdf",
            "course_code": "MA201",
            "course_name": "Calculus",
            "subject_name": "Math",
            "display_title": "MA201 Final",
            "url": "u2",
        },
    ]


def test_search_papers_exact_match():
    results = search_papers(_sample_papers(), "CS101")
    assert results
    assert results[0]["course_code"] == "CS101"


def test_search_papers_contains_match():
    results = search_papers(_sample_papers(), "calcul")
    assert any(p["course_code"] == "MA201" for p in results)


def test_search_papers_no_match_returns_empty():
    results = search_papers(_sample_papers(), "zzzzzz")
    assert results == []
