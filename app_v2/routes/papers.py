import time
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import HttpUrl

from ..models import CourseResponse, PaginationInfo, Paper, PapersResponse
from ..services.indexing import paper_index

router = APIRouter(prefix="/api/papers", tags=["Papers"])

YearFilter = Annotated[
    int | None, Query(ge=2000, le=2100, description="Filter by year")
]
SemesterFilter = Annotated[
    int | None, Query(ge=1, le=8, description="Filter by semester (1-8)")
]
ProgramFilter = Annotated[
    str | None, Query(max_length=50, description="Filter by program")
]
DegreeTypeFilter = Annotated[
    str | None, Query(max_length=50, description="Filter by degree type")
]
PaperTypeFilter = Annotated[
    str | None,
    Query(max_length=50, description="Filter by paper type (Regular, Makeup, etc.)"),
]
CourseCodeFilter = Annotated[
    str | None, Query(max_length=20, description="Filter by course code")
]
StreamFilter = Annotated[
    str | None, Query(max_length=20, description="Filter by stream (cs, core)")
]
ProgramAbbrevFilter = Annotated[
    str | None,
    Query(
        min_length=1,
        max_length=20,
        pattern=r"\S",
        description="Filter by program abbreviation (e.g., CSE, ECE)",
    ),
]
SearchQuery = Annotated[
    str | None, Query(min_length=2, max_length=100, description="Search query")
]
SortField = Annotated[
    Literal["year", "semester", "relevance"] | None,
    Query(description="Sort field: year, semester, or relevance"),
]
SortOrder = Annotated[
    Literal["asc", "desc"] | None,
    Query(description="Sort order: asc or desc (default: desc)"),
]
LimitParam = Annotated[
    int, Query(ge=1, le=500, description="Number of results per page")
]
OffsetParam = Annotated[int, Query(ge=0, description="Offset for pagination")]
LOOKUP_OPERATION_ID = "lookup_paper_api_papers_lookup_get"
YEAR_OPERATION_ID = "get_papers_by_year_api_papers_year__year__get"
COURSE_OPERATION_ID = "get_papers_by_course_api_papers_course__course_code__get"
SEMESTER_OPERATION_ID = "get_papers_by_semester_api_papers_semester__semester__get"


def _to_public_paper(paper: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in paper.items() if not k.startswith("_")}


def _create_paginated_response(
    papers: list[dict[str, Any]],
    limit: int,
    offset: int,
    execution_time: float | None = None,
) -> PapersResponse:
    paginated = papers[offset : offset + limit]
    total = len(papers)
    execution_time_ms = None if execution_time is None else round(execution_time, 2)

    return PapersResponse(
        papers=[Paper(**_to_public_paper(p)) for p in paginated],
        total=total,
        limit=limit,
        offset=offset,
        pagination=PaginationInfo(
            total=total,
            limit=limit,
            offset=offset,
            page=(offset // limit) + 1 if limit > 0 else 1,
            total_pages=max(1, (total + limit - 1) // limit) if limit > 0 else 1,
            has_next=offset + limit < total,
            has_prev=offset > 0,
        ),
        execution_time_ms=execution_time_ms,
    )


def _sort_papers(
    papers: list[dict[str, Any]],
    sort_field: str,
    order: str,
) -> list[dict[str, Any]]:
    if sort_field == "relevance":
        # Relevance order is already set by search results.
        # Reverse if ascending order is requested (relevance is naturally desc).
        return list(reversed(papers)) if order == "asc" else papers

    non_null = [p for p in papers if p.get(sort_field) is not None]
    non_null.sort(key=lambda p: p.get(sort_field, 0), reverse=order == "desc")
    return non_null + [p for p in papers if p.get(sort_field) is None]


def _intersect_filter_url_sets(filter_url_sets: list[set[str]]) -> set[str] | None:
    if not filter_url_sets:
        return None

    filter_url_sets.sort(key=len)
    if not filter_url_sets[0]:
        return set()
    return filter_url_sets[0].intersection(*filter_url_sets[1:])


async def _resolve_paper_results(
    search: str | None, filter_urls: set[str] | None
) -> list[dict[str, Any]]:
    if search:
        search_urls = await run_in_threadpool(paper_index._search, search)
        if filter_urls is not None:
            return paper_index._get_by_urls(
                [url for url in search_urls if url in filter_urls]
            )
        return paper_index._get_by_urls(search_urls)

    if filter_urls is not None:
        return paper_index._get_by_urls(filter_urls)
    return paper_index.papers


@router.get("", response_model=PapersResponse, operation_id="get_papers_api_papers_get")
async def _get_papers(
    year: YearFilter = None,
    semester: SemesterFilter = None,
    program: ProgramFilter = None,
    degree_type: DegreeTypeFilter = None,
    paper_type: PaperTypeFilter = None,
    course_code: CourseCodeFilter = None,
    stream: StreamFilter = None,
    program_abbrev: ProgramAbbrevFilter = None,
    search: SearchQuery = None,
    sort: SortField = None,
    order: SortOrder = None,
    limit: LimitParam = 50,
    offset: OffsetParam = 0,
) -> PapersResponse:
    """Get question papers with filtering, fuzzy search, sorting, and pagination."""
    start_time = time.time()

    filters = [
        (year, paper_index._get_urls_by_year),
        (semester, paper_index._get_urls_by_semester),
        (program, paper_index._get_urls_by_program),
        (course_code, paper_index._get_urls_by_course),
        (stream, paper_index._get_urls_by_stream),
        (degree_type, paper_index._get_urls_by_degree_type),
        (paper_type, paper_index._get_urls_by_paper_type),
        (program_abbrev, paper_index._get_urls_by_program_abbrev),
    ]

    filter_urls = _intersect_filter_url_sets(
        [method(value) for value, method in filters if value is not None]
    )
    if filter_urls is not None and not filter_urls:
        return _create_paginated_response(
            [], limit, offset, (time.time() - start_time) * 1000
        )

    results = await _resolve_paper_results(search, filter_urls)
    sort_field = sort or ("relevance" if search else "year")
    if sort_field == "relevance" and not search:
        sort_field = "year"
    results = _sort_papers(results, sort_field, order if order is not None else "desc")

    return _create_paginated_response(
        results, limit, offset, (time.time() - start_time) * 1000
    )


@router.get("/lookup", response_model=Paper, operation_id=LOOKUP_OPERATION_ID)
async def _lookup_paper(
    url: HttpUrl = Query(..., description="Exact paper URL to look up"),
) -> Paper:
    """Look up a single paper by its exact download URL."""
    paper = paper_index._get_by_url(str(url))
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return Paper(**_to_public_paper(paper))


@router.get(
    "/year/{year}", response_model=PapersResponse, operation_id=YEAR_OPERATION_ID
)
async def _get_papers_by_year(
    year: int = Path(..., ge=2000, le=2100, description="Academic Year"),
    semester: int | None = Query(None, ge=1, le=8),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> PapersResponse:
    """Get papers for a specific year with optional semester filter."""
    urls = paper_index._get_urls_by_year(year)

    if not urls:
        raise HTTPException(status_code=404, detail=f"No papers found for year {year}")

    if semester is not None:
        urls = urls.intersection(paper_index._get_urls_by_semester(semester))

    papers = paper_index._get_by_urls(urls)
    return _create_paginated_response(papers, limit, offset)


@router.get(
    "/course/{course_code}",
    response_model=CourseResponse,
    operation_id=COURSE_OPERATION_ID,
)
async def _get_papers_by_course(
    course_code: str = Path(..., max_length=20, description="Course code")
) -> CourseResponse:
    """Get all papers for a specific course code."""
    papers = paper_index._get_papers_by_course(course_code.upper())

    if not papers:
        raise HTTPException(
            status_code=404, detail=f"No papers found for course {course_code}"
        )

    return CourseResponse(
        course_code=course_code.upper(),
        course_name=papers[0].get("course_name"),
        papers=[Paper(**_to_public_paper(p)) for p in papers],
        total_papers=len(papers),
    )


@router.get(
    "/semester/{semester}",
    response_model=PapersResponse,
    operation_id=SEMESTER_OPERATION_ID,
)
async def _get_papers_by_semester(
    semester: int = Path(..., ge=1, le=8, description="Semester (1-8)"),
    year: int | None = Query(None, ge=2000, le=2100, description="Academic Year"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> PapersResponse:
    """Get papers for a specific semester with optional year filter."""
    urls = paper_index._get_urls_by_semester(semester)

    if year is not None:
        urls = urls.intersection(paper_index._get_urls_by_year(year))

    papers = paper_index._get_by_urls(urls)
    return _create_paginated_response(papers, limit, offset)
