"""Question-paper retrieval routes."""

import time
from typing import (
    Annotated,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    Set,
)

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import HttpUrl

from ..models import CourseResponse, PaginationInfo, Paper, PapersResponse
from ..services.indexing import paper_index

router = APIRouter(prefix="/api/papers", tags=["Papers"])

YearFilter = Annotated[
    Optional[int], Query(ge=2000, le=2100, description="Filter by year")
]
SemesterFilter = Annotated[
    Optional[int], Query(ge=1, le=8, description="Filter by semester (1-8)")
]
ProgramFilter = Annotated[
    Optional[str], Query(max_length=50, description="Filter by program")
]
DegreeTypeFilter = Annotated[
    Optional[str], Query(max_length=50, description="Filter by degree type")
]
PaperTypeFilter = Annotated[
    Optional[str],
    Query(max_length=50, description="Filter by paper type (Regular, Makeup, etc.)"),
]
CourseCodeFilter = Annotated[
    Optional[str], Query(max_length=20, description="Filter by course code")
]
StreamFilter = Annotated[
    Optional[str], Query(max_length=20, description="Filter by stream (cs, core)")
]
ProgramAbbrevFilter = Annotated[
    Optional[str],
    Query(
        min_length=1,
        max_length=20,
        pattern=r"\S",
        description="Filter by program abbreviation (e.g., CSE, ECE)",
    ),
]
SearchQuery = Annotated[
    Optional[str], Query(min_length=2, max_length=100, description="Search query")
]
SortField = Annotated[
    Optional[Literal["year", "semester", "relevance"]],
    Query(description="Sort field: year, semester, or relevance"),
]
SortOrder = Annotated[
    Optional[Literal["asc", "desc"]],
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


def _to_public_paper(paper: Dict[str, Any]) -> Dict[str, Any]:
    """Strip internal-only fields before serializing API responses."""
    return {k: v for k, v in paper.items() if not k.startswith("_")}


def _create_pagination(total: int, limit: int, offset: int) -> PaginationInfo:
    """Create pagination metadata from total, limit, and offset."""
    total_pages = max(1, (total + limit - 1) // limit) if limit > 0 else 1
    current_page = (offset // limit) + 1 if limit > 0 else 1

    return PaginationInfo(
        total=total,
        limit=limit,
        offset=offset,
        page=current_page,
        total_pages=total_pages,
        has_next=offset + limit < total,
        has_prev=offset > 0,
    )


def _create_paginated_response(
    papers: List[Dict[str, Any]],
    total: int,
    limit: int,
    offset: int,
    execution_time: Optional[float] = None,
) -> PapersResponse:
    """Create a standardized paginated response."""
    paginated = papers[offset : offset + limit]

    return PapersResponse(
        papers=[Paper(**_to_public_paper(p)) for p in paginated],
        total=total,
        limit=limit,
        offset=offset,
        pagination=_create_pagination(total, limit, offset),
        execution_time_ms=(
            round(execution_time, 2) if execution_time is not None else None
        ),
    )


def _sort_papers(
    papers: List[Dict[str, Any]],
    sort_field: str,
    order: str,
) -> List[Dict[str, Any]]:
    """Sort papers with null values placed after non-null values."""
    if not papers:
        return papers

    if sort_field == "relevance":
        # Relevance order is already set by search results.
        # Reverse if ascending order is requested (relevance is naturally desc).
        if order == "asc":
            return list(reversed(papers))
        return papers

    reverse = order == "desc"

    # Split into non-null and null groups to guarantee nulls always come last
    non_null = [p for p in papers if p.get(sort_field) is not None]
    nulls = [p for p in papers if p.get(sort_field) is None]

    non_null.sort(key=lambda p: p.get(sort_field, 0), reverse=reverse)

    return non_null + nulls


def _get_papers_response_from_urls(
    urls: set, limit: int, offset: int
) -> PapersResponse:
    """Helper to fetch papers by URL set and return a paginated response."""
    papers = paper_index.get_by_urls(urls)
    total = len(papers)
    return _create_paginated_response(papers, total, limit, offset)


def _collect_filter_url_sets(
    filters: Iterable[tuple[Any, Callable[[Any], Set[str]]]],
) -> List[Set[str]]:
    """Resolve active query filters to indexed URL sets."""
    return [method(value) for value, method in filters if value is not None]


def _intersect_filter_url_sets(filter_url_sets: List[Set[str]]) -> Optional[Set[str]]:
    """Intersect filter URL sets, using the smallest sets first."""
    if not filter_url_sets:
        return None

    filter_url_sets.sort(key=len)
    if not filter_url_sets[0]:
        return set()
    return filter_url_sets[0].intersection(*filter_url_sets[1:])


async def _resolve_paper_results(
    search: Optional[str], filter_urls: Optional[Set[str]]
) -> List[Dict[str, Any]]:
    """Resolve search/filter combinations into ordered paper dictionaries."""
    if search:
        search_urls = await run_in_threadpool(paper_index.search, search)
        if filter_urls is not None:
            return paper_index.get_by_urls(
                [url for url in search_urls if url in filter_urls]
            )
        return paper_index.get_by_urls(search_urls)

    if filter_urls is not None:
        return paper_index.get_by_urls(filter_urls)
    return paper_index.papers


def _effective_sort_field(
    sort: Optional[Literal["year", "semester", "relevance"]], search: Optional[str]
) -> Literal["year", "semester", "relevance"]:
    """Return the sort field implied by the request parameters."""
    if sort is None:
        return "relevance" if search else "year"
    if sort == "relevance" and not search:
        return "year"
    return sort


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
        (year, paper_index.get_urls_by_year),
        (semester, paper_index.get_urls_by_semester),
        (program, paper_index._get_urls_by_program),
        (course_code, paper_index.get_urls_by_course),
        (stream, paper_index._get_urls_by_stream),
        (degree_type, paper_index.get_urls_by_degree_type),
        (paper_type, paper_index.get_urls_by_paper_type),
        (program_abbrev, paper_index._get_urls_by_program_abbrev),
    ]

    filter_urls = _intersect_filter_url_sets(_collect_filter_url_sets(filters))
    if filter_urls is not None and not filter_urls:
        execution_time = (time.time() - start_time) * 1000
        return _create_paginated_response([], 0, limit, offset, execution_time)

    results = await _resolve_paper_results(search, filter_urls)
    effective_sort = _effective_sort_field(sort, search)
    effective_order = order if order is not None else "desc"
    results = _sort_papers(results, effective_sort, effective_order)

    # Get total before pagination
    total = len(results)

    execution_time = (time.time() - start_time) * 1000

    return _create_paginated_response(results, total, limit, offset, execution_time)


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
    semester: Optional[int] = Query(None, ge=1, le=8),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> PapersResponse:
    """Get papers for a specific year with optional semester filter."""
    urls = paper_index.get_urls_by_year(year)

    if not urls:
        raise HTTPException(status_code=404, detail=f"No papers found for year {year}")

    if semester is not None:
        urls = urls.intersection(paper_index.get_urls_by_semester(semester))

    return _get_papers_response_from_urls(urls, limit, offset)


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

    course_name = papers[0].get("course_name") if papers else None

    return CourseResponse(
        course_code=course_code.upper(),
        course_name=course_name,
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
    year: Optional[int] = Query(None, ge=2000, le=2100, description="Academic Year"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> PapersResponse:
    """Get papers for a specific semester with optional year filter."""
    urls = paper_index.get_urls_by_semester(semester)

    if year is not None:
        urls = urls.intersection(paper_index.get_urls_by_year(year))

    return _get_papers_response_from_urls(urls, limit, offset)
