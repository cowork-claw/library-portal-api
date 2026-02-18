import pytest

from app_v2.services.search import _calculate_relevance, _tokenize_words, search_papers


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


def test_search_papers_uses_precomputed_meta():
    papers = [
        {
            "url": "u-meta",
            "file_name": "fallback-name.pdf",
            "_search_meta": {
                "course_name": {
                    "lower": "algorithms and data structures",
                    "words": {"algorithms", "and", "data", "structures"},
                }
            },
        }
    ]

    results = search_papers(papers, "algorithms")
    assert len(results) == 1
    assert results[0]["url"] == "u-meta"


def test_search_papers_punctuation_query_returns_empty():
    results = search_papers(_sample_papers(), "!!!")
    assert results == []


def test_calculate_relevance_keeps_higher_previous_score_on_later_exact_match(
    monkeypatch,
):
    paper = {
        "course_code": "CS102",
        "course_name": "No match",
        "subject_name": "No match",
        "display_title": "target",
        "file_name": "none.pdf",
    }

    def fake_wratio(query, value):
        if value == "cs102":
            return 95
        return 0

    monkeypatch.setattr("app_v2.services.search.fuzz.WRatio", fake_wratio)

    score = _calculate_relevance(paper, "target", _tokenize_words("target"))
    assert score == pytest.approx(0.95)


def test_calculate_relevance_stops_when_remaining_fields_cannot_beat_max(monkeypatch):
    paper = {
        "course_code": "CS101",
        "course_name": "Calculus",
        "subject_name": "Math",
        "display_title": "Display",
        "file_name": "file.pdf",
    }

    def fake_wratio(query, value):
        if value == "cs101":
            return 96
        raise AssertionError("Lower-priority fields should not be scored")

    monkeypatch.setattr("app_v2.services.search.fuzz.WRatio", fake_wratio)

    score = _calculate_relevance(paper, "query", _tokenize_words("query"))
    assert score == pytest.approx(0.96)
