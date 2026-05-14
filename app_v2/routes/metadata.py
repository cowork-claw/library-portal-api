from fastapi import APIRouter

from ..models import MetadataResponse, StatisticsResponse
from ..services.indexing import paper_index

router = APIRouter(prefix="/api", tags=["Metadata"])
METADATA_OPERATION_ID = "get_metadata_api_metadata_get"
STATISTICS_OPERATION_ID = "get_statistics_api_statistics_get"


@router.get(
    "/metadata", response_model=MetadataResponse, operation_id=METADATA_OPERATION_ID
)
async def _get_metadata() -> MetadataResponse:
    """Return available filter values for clients."""
    return MetadataResponse(
        years=list(paper_index._unique_year_values),
        programs=list(paper_index._unique_program_values),
        program_abbrevs=list(paper_index._unique_program_abbrev_values),
        semesters=list(paper_index._unique_semester_values),
        paper_types=list(paper_index._unique_paper_type_values),
        degree_types=list(paper_index._unique_degree_type_values),
        course_codes=list(paper_index._unique_course_code_values[:100]),  # Limit to 100
        streams=list(paper_index._unique_stream_values),
        total_papers=paper_index._paper_count,
    )


@router.get(
    "/statistics",
    response_model=StatisticsResponse,
    operation_id=STATISTICS_OPERATION_ID,
)
async def _get_statistics() -> StatisticsResponse:
    """Return aggregate paper collection counts."""
    return StatisticsResponse(
        total_papers=paper_index._paper_count,
        papers_by_year=dict(paper_index._count_by_year_values),
        papers_by_program=dict(paper_index._count_by_program_values),
        papers_by_program_abbrev=dict(paper_index._count_by_program_abbrev_values),
        papers_by_semester=dict(paper_index._count_by_semester_values),
        courses_count=len(paper_index._unique_course_code_values),
        files_loaded=paper_index._loaded_file_count,
    )
