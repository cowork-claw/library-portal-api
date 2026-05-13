"""Metadata and collection statistics routes."""

from fastapi import APIRouter

from ..models import MetadataResponse, StatisticsResponse
from ..services.indexing import paper_index

router = APIRouter(prefix="/api", tags=["Metadata"])


@router.get(
    "/metadata",
    response_model=MetadataResponse,
    operation_id="get_metadata_api_metadata_get",
)
async def _get_metadata() -> MetadataResponse:
    """Return available filter values for clients."""
    return MetadataResponse(
        years=list(paper_index.unique_years),
        programs=list(paper_index.unique_programs),
        program_abbrevs=list(paper_index.unique_program_abbrevs),
        semesters=list(paper_index.unique_semesters),
        paper_types=list(paper_index.unique_paper_types),
        degree_types=list(paper_index.unique_degree_types),
        course_codes=list(paper_index.unique_course_codes[:100]),  # Limit to 100
        streams=list(paper_index.unique_streams),
        total_papers=paper_index.total_papers,
    )


@router.get(
    "/statistics",
    response_model=StatisticsResponse,
    operation_id="get_statistics_api_statistics_get",
)
async def _get_statistics() -> StatisticsResponse:
    """Return aggregate paper collection counts."""
    return StatisticsResponse(
        total_papers=paper_index.total_papers,
        papers_by_year=dict(paper_index.count_by_year),
        papers_by_program=dict(paper_index.count_by_program),
        papers_by_program_abbrev=dict(paper_index.count_by_program_abbrev),
        papers_by_semester=dict(paper_index.count_by_semester),
        courses_count=len(paper_index.unique_course_codes),
        files_loaded=paper_index.files_loaded,
    )
