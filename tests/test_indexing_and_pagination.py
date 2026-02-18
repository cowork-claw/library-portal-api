import json
from asyncio import run

from app_v2.data_loader import DataLoader
from app_v2.routes import papers as papers_route
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


def test_index_build_search_meta_excludes_empty_tokens():
    papers = _sample_papers()
    papers[0]["course_name"] = "Algorithms!!!"

    index = PaperIndex()
    index.papers = papers
    index._build_indexes()

    meta = papers[0]["_search_meta"]["course_name"]
    assert "algorithms" in meta["words"]
    assert "" not in meta["words"]


def test_create_paginated_response_hides_internal_fields():
    papers = _sample_papers()
    papers[0]["_search_meta"] = {"course_name": {"lower": "x", "words": {"x"}}}

    response = create_paginated_response(papers, total=3, limit=1, offset=0)
    serialized = response.model_dump()

    assert "_search_meta" not in serialized["papers"][0]


def test_load_from_directory_releases_loader_caches_without_touching_index(tmp_path):
    data_file = tmp_path / "papers.json"
    data_file.write_text(
        json.dumps({"CS101": [{"url": "u1", "course_code": "CS101"}]}),
        encoding="utf-8",
    )

    loader = DataLoader(tmp_path)
    index = PaperIndex()
    index.load_from_directory(loader)

    assert len(index.papers) == 1
    assert index.papers[0]["url"] == "u1"
    assert loader.papers == []
    assert loader.papers_by_url == {}


def test_get_papers_unfiltered_uses_direct_index_reference(monkeypatch):
    source = [{"url": "u1", "course_code": "CS101"}]
    captured = {}

    def fake_create_paginated_response(
        papers, total, limit, offset, execution_time=None
    ):
        captured["papers"] = papers
        return {"ok": True}

    monkeypatch.setattr(papers_route.paper_index, "papers", source)
    monkeypatch.setattr(
        papers_route, "create_paginated_response", fake_create_paginated_response
    )

    run(
        papers_route.get_papers(
            year=None,
            semester=None,
            program=None,
            degree_type=None,
            paper_type=None,
            course_code=None,
            stream=None,
            search=None,
            limit=50,
            offset=0,
        )
    )

    assert captured["papers"] is source
