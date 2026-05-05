"""
Papers Routes for Library Portal API V2

Endpoints for retrieving and searching question papers.
"""

import time
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import HttpUrl

from ..models import CourseResponse, PaginationInfo, Paper, PapersResponse
from ..services.indexing import paper_index

router = APIRouter(prefix="/api/papers", tags=["Papers"])


def to_public_paper(paper: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strip internal-only fields before serializing API responses.

    Args:
        paper: The internal paper dictionary.

    Returns:
        A dictionary suitable for public API exposure.
    """
    return {k: v for k, v in paper.items() if not k.startswith("_")}


def create_pagination(total: int, limit: int, offset: int) -> PaginationInfo:
    """
    Create pagination info from parameters.

    Args:
        total: Total number of items.
        limit: Max items per page.
        offset: Number of items skipped.

    Returns:
        A PaginationInfo model with pagination metadata.
    """
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


def create_paginated_response(
    papers: List[Dict[str, Any]],
    total: int,
    limit: int,
    offset: int,
    execution_time: Optional[float] = None,
) -> PapersResponse:
    """Create a standardized paginated response."""
    paginated = papers[offset : offset + limit]

    return PapersResponse(
        papers=[Paper(**to_public_paper(p)) for p in paginated],
        total=total,
        limit=limit,
        offset=offset,
        pagination=create_pagination(total, limit, offset),
        execution_time_ms=(
            round(execution_time, 2) if execution_time is not None else None
        ),
    )


def _sort_papers(
    papers: List[Dict[str, Any]],
    sort_field: str,
    order: str,
) -> List[Dict[str, Any]]:
    """Sort papers by the specified field and order.

    Args:
        papers: List of paper dictionaries to sort.
        sort_field: One of 'year', 'semester', 'relevance'.
        order: One of 'asc', 'desc'.

    Returns:
        A new list of papers sorted accordingly. Papers with null values
        for the sort field are placed after all non-null papers.
    """
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
    return create_paginated_response(papers, total, limit, offset)


@router.get("", response_model=PapersResponse)
async def get_papers(
    # Filters
    year: Optional[int] = Query(None, ge=2000, le=2100, description="Filter by year"),
    semester: Optional[int] = Query(
        None, ge=1, le=8, description="Filter by semester (1-8)"
    ),
    program: Optional[str] = Query(
        None, max_length=50, description="Filter by program"
    ),
    degree_type: Optional[str] = Query(
        None, max_length=50, description="Filter by degree type"
    ),
    paper_type: Optional[str] = Query(
        None, max_length=50, description="Filter by paper type (Regular, Makeup, etc.)"
    ),
    course_code: Optional[str] = Query(
        None, max_length=20, description="Filter by course code"
    ),
    stream: Optional[str] = Query(
        None, max_length=20, description="Filter by stream (cs, core)"
    ),
    program_abbrev: Optional[str] = Query(
        None,
        min_length=1,
        max_length=20,
        pattern=r"\S",
        description="Filter by program abbreviation (e.g., CSE, ECE)",
    ),
    # Search
    search: Optional[str] = Query(
        None, min_length=2, max_length=100, description="Search query"
    ),
    # Sort
    sort: Optional[Literal["year", "semester", "relevance"]] = Query(
        None, description="Sort field: year, semester, or relevance"
    ),
    order: Optional[Literal["asc", "desc"]] = Query(
        None, description="Sort order: asc or desc (default: desc)"
    ),
    # Pagination
    limit: int = Query(50, ge=1, le=500, description="Number of results per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> PapersResponse:
    """
    Get question papers with optional filtering, search, and pagination.

    Filters can be combined. Search uses fuzzy matching on course names and titles.

    Args:
        year: Filter by academic year.
        semester: Filter by semester number (1-8).
        program: Filter by program name (e.g., "B.Tech Computer Science").
        degree_type: Filter by degree type (e.g., "B.Tech", "M.Tech").
        paper_type: Filter by paper type (e.g., "Regular", "Makeup").
        course_code: Filter by exact course code.
        stream: Filter by stream (e.g., "cs", "core").
        program_abbrev: Filter by program abbreviation (e.g., "CSE", "ECE").
        search: Search query for fuzzy matching.
        sort: Sort field — one of 'year', 'semester', 'relevance'.
            Defaults to 'relevance' when search is provided, otherwise 'year'.
        order: Sort order — 'asc' or 'desc'. Defaults to 'desc'.
        limit: Number of results to return per page.
        offset: Number of results to skip (for pagination).

    Returns:
        PapersResponse: Paginated list of matching papers with metadata.
    """
    start_time = time.time()

    # Efficiently filter papers using URL sets from indexes
    filter_url_sets = []

    filters = [
        (year, paper_index.get_urls_by_year),
        (semester, paper_index.get_urls_by_semester),
        (program, paper_index.get_urls_by_program),
        (course_code, paper_index.get_urls_by_course),
        (stream, paper_index.get_urls_by_stream),
        (degree_type, paper_index.get_urls_by_degree_type),
        (paper_type, paper_index.get_urls_by_paper_type),
        (program_abbrev, paper_index.get_urls_by_program_abbrev),
    ]

    for value, method in filters:
        if value is not None:
            filter_url_sets.append(method(value))

    # Intersect filter results if multiple filters are active
    filter_urls = None
    if filter_url_sets:
        # Sort by set size for faster intersection (smallest first)
        filter_url_sets.sort(key=len)
        # Early exit if any filter returned empty
        if len(filter_url_sets[0]) == 0:
            execution_time = (time.time() - start_time) * 1000
            return create_paginated_response([], 0, limit, offset, execution_time)
        filter_urls = filter_url_sets[0].intersection(*filter_url_sets[1:])

    # Apply search if provided
    if search:
        # Use cached global search (returns sorted URLs)
        # Offload to threadpool to avoid blocking event loop during first computation
        search_urls = await run_in_threadpool(paper_index.search, search)

        if filter_urls is not None:
            # Combine search + filters (intersection), preserving search rank
            # Note: We iterate over sorted search_urls to maintain relevance order
            results = paper_index.get_by_urls(
                [url for url in search_urls if url in filter_urls]
            )
        else:
            results = paper_index.get_by_urls(search_urls)

    else:
        # No search, just filters
        if filter_urls is not None:
            results = paper_index.get_by_urls(filter_urls)
        else:
            results = paper_index.papers

    # Determine effective sort field and order
    effective_sort = sort
    if effective_sort is None:
        effective_sort = "relevance" if search else "year"
    elif effective_sort == "relevance" and not search:
        # Relevance sort without search falls back to year descending
        effective_sort = "year"

    effective_order = order if order is not None else "desc"

    # Apply sorting
    results = _sort_papers(results, effective_sort, effective_order)

    # Get total before pagination
    total = len(results)

    execution_time = (time.time() - start_time) * 1000

    return create_paginated_response(results, total, limit, offset, execution_time)


@router.get("/lookup", response_model=Paper)
async def lookup_paper(
    url: HttpUrl = Query(..., description="Exact paper URL to look up"),
) -> Paper:
    """
    Look up a single paper by its exact download URL.

    Args:
        url: The exact URL of the paper to find.

    Returns:
        Paper: The matching paper object.

    Raises:
        HTTPException: 404 if no paper with the given URL exists in the index.
    """
    paper = paper_index.get_by_url(str(url))
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return Paper(**to_public_paper(paper))


@router.get("/year/{year}", response_model=PapersResponse)
async def get_papers_by_year(
    year: int = Path(..., ge=2000, le=2100, description="Academic Year"),
    semester: Optional[int] = Query(None, ge=1, le=8),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> PapersResponse:
    """Get papers for a specific year with optional semester filter."""
    urls = paper_index.get_urls_by_year(year)

    if not urls:
        # Note: get_papers returns empty list, but this endpoint historically returns 404
        # We preserve this behavior.
        raise HTTPException(status_code=404, detail=f"No papers found for year {year}")

    if semester is not None:
        urls = urls.intersection(paper_index.get_urls_by_semester(semester))

    return _get_papers_response_from_urls(urls, limit, offset)


@router.get("/course/{course_code}", response_model=CourseResponse)
async def get_papers_by_course(
    course_code: str = Path(..., max_length=20, description="Course code")
) -> CourseResponse:
    """Get all papers for a specific course code."""
    papers = paper_index.get_papers_by_course(course_code.upper())

    if not papers:
        raise HTTPException(
            status_code=404, detail=f"No papers found for course {course_code}"
        )

    # Get course name from first paper
    course_name = papers[0].get("course_name") if papers else None

    return CourseResponse(
        course_code=course_code.upper(),
        course_name=course_name,
        papers=[Paper(**to_public_paper(p)) for p in papers],
        total_papers=len(papers),
    )


@router.get("/semester/{semester}", response_model=PapersResponse)
async def get_papers_by_semester(
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
