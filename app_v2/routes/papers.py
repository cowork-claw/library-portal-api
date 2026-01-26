"""
Papers Routes for Library Portal API V2

Endpoints for retrieving and searching question papers.
"""

import time
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, HTTPException

from ..models import Paper, PapersResponse, PaginationInfo, CourseResponse
from ..services.indexing import paper_index
from ..services.search import search_papers

router = APIRouter(prefix="/api/papers", tags=["Papers"])


def create_pagination(total: int, limit: int, offset: int) -> PaginationInfo:
    """Create pagination info from parameters."""
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
        papers=[Paper(**p) for p in paginated],
        total=total,
        limit=limit,
        offset=offset,
        pagination=create_pagination(total, limit, offset),
        execution_time_ms=(
            round(execution_time, 2) if execution_time is not None else None
        ),
    )


@router.get("", response_model=PapersResponse)
async def get_papers(
    # Filters
    year: Optional[int] = Query(None, description="Filter by year"),
    semester: Optional[int] = Query(
        None, ge=1, le=8, description="Filter by semester (1-8)"
    ),
    program: Optional[str] = Query(None, description="Filter by program"),
    degree_type: Optional[str] = Query(None, description="Filter by degree type"),
    paper_type: Optional[str] = Query(
        None, description="Filter by paper type (Regular, Makeup, etc.)"
    ),
    course_code: Optional[str] = Query(None, description="Filter by course code"),
    stream: Optional[str] = Query(None, description="Filter by stream (cs, core)"),
    # Search
    search: Optional[str] = Query(None, min_length=2, description="Search query"),
    # Pagination
    limit: int = Query(50, ge=1, le=500, description="Number of results per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
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
        search: Search query for fuzzy matching.
        limit: Number of results to return per page.
        offset: Number of results to skip (for pagination).

    Returns:
        PapersResponse: Paginated list of matching papers with metadata.
    """
    start_time = time.time()

    # Efficiently filter papers using URL sets from indexes
    filter_url_sets = []

    if year is not None:
        filter_url_sets.append(paper_index.get_urls_by_year(year))

    if semester is not None:
        filter_url_sets.append(paper_index.get_urls_by_semester(semester))

    if program is not None:
        filter_url_sets.append(paper_index.get_urls_by_program(program))

    if course_code is not None:
        filter_url_sets.append(paper_index.get_urls_by_course(course_code))

    if stream is not None:
        filter_url_sets.append(paper_index.get_urls_by_stream(stream))

    # Intersect filter results if multiple filters are active
    if filter_url_sets:
        # Start with the first set and intersect with the rest
        intersected_urls = filter_url_sets[0].intersection(*filter_url_sets[1:])
        results = paper_index.get_by_urls(intersected_urls)
    else:
        results = list(paper_index.papers)

    # Slower, non-indexed filters (apply after indexed filters)
    if degree_type is not None:
        results = [p for p in results if p.get("degree_type") == degree_type]

    if paper_type is not None:
        results = [p for p in results if p.get("paper_type") == paper_type]

    # Apply search if provided
    if search:
        results = search_papers(results, search)

    # Get total before pagination
    total = len(results)

    execution_time = (time.time() - start_time) * 1000

    return create_paginated_response(results, total, limit, offset, execution_time)


@router.get("/year/{year}", response_model=PapersResponse)
async def get_papers_by_year(
    year: int,
    semester: Optional[int] = Query(None, ge=1, le=8),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get papers for a specific year with optional semester filter."""
    urls = paper_index.get_urls_by_year(year)
    papers = paper_index.get_by_urls(urls)

    if not papers:
        raise HTTPException(status_code=404, detail=f"No papers found for year {year}")

    if semester is not None:
        papers = [p for p in papers if p.get("semester") == semester]

    total = len(papers)

    return create_paginated_response(papers, total, limit, offset)


@router.get("/course/{course_code}", response_model=CourseResponse)
async def get_papers_by_course(course_code: str):
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
        papers=[Paper(**p) for p in papers],
        total_papers=len(papers),
    )


@router.get("/semester/{semester}", response_model=PapersResponse)
async def get_papers_by_semester(
    semester: int,
    year: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get papers for a specific semester with optional year filter."""
    if semester < 1 or semester > 8:
        raise HTTPException(status_code=400, detail="Semester must be between 1 and 8")

    urls = paper_index.get_urls_by_semester(semester)
    papers = paper_index.get_by_urls(urls)

    if year is not None:
        papers = [p for p in papers if p.get("year") == year]

    total = len(papers)

    return create_paginated_response(papers, total, limit, offset)
