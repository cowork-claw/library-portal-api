from app_v2.routes.papers import _create_paginated_response
from app_v2.services.indexing import PaperIndex


def _sample_papers():
    return [
        {
            "file_name": "cs101-midterm.pdf",
            "url": "u1",
            "year": 2024,
            "semester": 1,
            "course_code": "CS101",
            "degree_type": "B.Tech",
            "program_abbrev": "CSE",
            "streams": ["cs"],
            "paper_type": "Regular",
        },
        {
            "file_name": "ma201-final.pdf",
            "url": "u2",
            "year": 2024,
            "semester": 2,
            "course_code": "MA201",
            "degree_type": "B.Tech",
            "program_abbrev": "CSE",
            "streams": ["core"],
            "paper_type": "Regular",
        },
        {
            "file_name": "ee101-quiz.pdf",
            "url": "u3",
            "year": 2023,
            "semester": 1,
            "course_code": "EE101",
            "degree_type": "B.Tech",
            "program_abbrev": "ECE",
            "streams": ["core"],
            "paper_type": "Makeup",
        },
    ]


def test_indexing_urls_and_program_abbrevs():
    index = PaperIndex()
    index.papers = _sample_papers()
    index._build_indexes()

    assert index._get_urls_by_year(2024) == {"u1", "u2"}
    assert index._get_urls_by_course("cs101") == {"u1"}
    assert index._get_urls_by_paper_type("Regular") == {"u1", "u2"}
    assert index._get_urls_by_degree_type("B.Tech") == {"u1", "u2", "u3"}
    assert set(index._unique_program_abbrev_values) == {"CSE", "ECE"}
    assert index._count_by_program_abbrev_values["CSE"] == 2


def test_program_and_degree_type_indexes_stay_separate():
    index = PaperIndex()
    index.papers = [
        {
            "file_name": "cs101-midterm.pdf",
            "url": "u1",
            "program": "Computer Science",
            "degree_type": "B.Tech",
        }
    ]
    index._build_indexes()

    assert index._get_urls_by_program("Computer Science") == {"u1"}
    assert index._get_urls_by_degree_type("B.Tech") == {"u1"}
    assert index._unique_program_values == ("Computer Science",)


def test_pagination_info_and_response():
    papers = _sample_papers()
    response = _create_paginated_response(papers, limit=2, offset=2)

    assert response.pagination.total_pages == 2
    assert response.pagination.has_next is False
    assert response.pagination.has_prev is True
    assert response.pagination.page == 2
    assert len(response.papers) == 1


def test_index_build_search_meta_excludes_empty_tokens():
    papers = _sample_papers()
    papers[0]["course_name"] = "Algorithms!!!"

    index = PaperIndex()
    index.papers = papers
    index._build_indexes()

    meta = papers[0]["_search_meta"]["course_name"]
    assert "algorithms" in meta["words"]
    assert "" not in meta["words"]


def test_index_build_search_meta_reuses_cached_metadata_for_same_value():
    papers = _sample_papers()
    papers[0]["course_name"] = "Algorithms"
    papers[1]["course_name"] = "Algorithms"
    papers[2]["course_name"] = "Circuits"

    index = PaperIndex()
    index.papers = papers
    index._build_indexes()

    first_meta = papers[0]["_search_meta"]["course_name"]
    second_meta = papers[1]["_search_meta"]["course_name"]
    third_meta = papers[2]["_search_meta"]["course_name"]

    assert first_meta is second_meta
    assert first_meta is not third_meta


def test_create_paginated_response_hides_internal_fields():
    papers = _sample_papers()
    papers[0]["_search_meta"] = {"course_name": {"lower": "x", "words": {"x"}}}

    response = _create_paginated_response(papers, limit=1, offset=0)
    serialized = response.model_dump()

    assert "_search_meta" not in serialized["papers"][0]
