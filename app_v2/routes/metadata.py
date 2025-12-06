"""
Metadata Routes for Library Portal API V2

Endpoints for retrieving available filter values and statistics.
"""

from fastapi import APIRouter

from ..models import MetadataResponse, StatisticsResponse
from ..services.indexing import paper_index

router = APIRouter(prefix="/api", tags=["Metadata"])


@router.get("/metadata", response_model=MetadataResponse)
async def get_metadata():
    """
    Get available filter values.
    
    Returns all unique values for each filter field, useful for building
    filter dropdowns in the frontend.
    """
    return MetadataResponse(
        years=paper_index.unique_years,
        programs=paper_index.unique_programs,
        semesters=paper_index.unique_semesters,
        paper_types=paper_index.unique_paper_types,
        degree_types=paper_index.unique_degree_types,
        course_codes=paper_index.unique_course_codes[:100],  # Limit to 100
        streams=paper_index.unique_streams,
        total_papers=paper_index.total_papers
    )


@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics():
    """
    Get detailed statistics about the paper collection.
    
    Includes counts by year, program, semester, and overall totals.
    """
    return StatisticsResponse(
        total_papers=paper_index.total_papers,
        papers_by_year=paper_index.count_by_year,
        papers_by_program=paper_index.count_by_program,
        papers_by_semester=paper_index.count_by_semester,
        courses_count=len(paper_index.unique_course_codes),
        files_loaded=paper_index.files_loaded
    )
