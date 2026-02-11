from app_v2.routes.papers import create_paginated_response, create_pagination
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

    assert index.get_urls_by_year(2024) == {"u1", "u2"}
    assert index.get_urls_by_course("cs101") == {"u1"}
    assert index.get_urls_by_paper_type("Regular") == {"u1", "u2"}
    assert index.get_urls_by_degree_type("B.Tech") == {"u1", "u2", "u3"}
    assert set(index.unique_program_abbrevs) == {"CSE", "ECE"}
    assert index.count_by_program_abbrev["CSE"] == 2


def test_pagination_info_and_response():
    papers = _sample_papers()
    pagination = create_pagination(total=3, limit=2, offset=0)
    assert pagination.total_pages == 2
    assert pagination.has_next is True
    assert pagination.has_prev is False

    response = create_paginated_response(papers, total=3, limit=2, offset=2)
    assert response.pagination.page == 2
    assert len(response.papers) == 1


def test_index_build_keeps_search_meta_out_of_paper_payload():
    papers = _sample_papers()
    papers[0]["course_name"] = "Algorithms!!!"

    index = PaperIndex()
    index.papers = papers
    index._build_indexes()

    assert "_search_meta" not in papers[0]

    meta = index.search_meta_by_url["u1"]["course_name"]
    assert "algorithms" in meta["words"]
    assert "" not in meta["words"]
