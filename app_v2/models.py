"""
Pydantic Models for Library Portal API V2

Clean, simplified models for request/response handling.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# =============================================================================
# PAPER MODELS
# =============================================================================


class CurriculumContext(BaseModel):
    """Curriculum context indicating which students a paper is relevant for."""

    curriculum_id: Optional[str] = None
    valid_for_streams: List[str] = Field(default_factory=lambda: ["all"])
    valid_for_batches: List[int] = Field(default_factory=list)
    valid_for_branches: Optional[List[str]] = None


class Paper(BaseModel):
    """Single question paper."""

    # File info
    file_name: str
    url: Optional[str] = None
    path: Optional[str] = None
    display_title: Optional[str] = None

    # Core identification
    year: Optional[int] = None
    semester: Optional[int] = None
    session: Optional[str] = None  # "Even (May/Jun)" or "Odd (Nov/Dec)"
    paper_type: Optional[str] = None  # "Regular", "Supplementary", "Makeup"

    # Course info
    course_code: Optional[str] = None
    course_name: Optional[str] = None
    subject_code: Optional[str] = None  # Backwards compat
    subject_name: Optional[str] = None  # Backwards compat

    # Program info
    program: Optional[str] = None
    program_abbrev: Optional[str] = None
    program_name: Optional[str] = None
    degree_type: Optional[str] = None
    program_category: Optional[str] = None
    specialization: Optional[str] = None
    college: Optional[str] = None

    # Curriculum context (V2)
    curriculum_context: Optional[CurriculumContext] = None
    streams: Optional[List[str]] = None

    # Metadata
    scraped_at: Optional[str] = None

    class Config:
        extra = "allow"  # Allow extra fields from JSON


# =============================================================================
# PAGINATION MODELS
# =============================================================================


class PaginationInfo(BaseModel):
    """Pagination metadata."""

    total: int
    limit: int
    offset: int
    page: int
    total_pages: int
    has_next: bool
    has_prev: bool


# =============================================================================
# RESPONSE MODELS
# =============================================================================


class PapersResponse(BaseModel):
    """Response for papers endpoint."""

    papers: List[Paper]
    total: int
    limit: int
    offset: int
    pagination: PaginationInfo
    execution_time_ms: Optional[float] = None


class MetadataResponse(BaseModel):
    """Response for metadata endpoint - available filter values."""

    years: List[int]
    programs: List[str]
    program_abbrevs: List[str]
    semesters: List[int]
    paper_types: List[str]
    degree_types: List[str]
    course_codes: List[str]
    streams: List[str]
    total_papers: int


class CourseResponse(BaseModel):
    """Response for single course endpoint."""

    course_code: str
    course_name: Optional[str]
    papers: List[Paper]
    total_papers: int


# =============================================================================
# HEALTH MODELS
# =============================================================================


class ComponentHealth(BaseModel):
    """Health status of a single component."""

    status: str  # "healthy", "degraded", "unhealthy"
    message: str
    details: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Response for health check endpoints."""

    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: str
    version: str
    uptime_seconds: float
    components: Dict[str, ComponentHealth]


class DataHealthResponse(BaseModel):
    """Response for data health endpoint."""

    status: str
    total_papers: int
    unique_urls: int
    files_loaded: int
    courses_count: int
    last_loaded: Optional[str]
    errors: List[str]
    papers_by_year: Dict[int, int]
    papers_by_program: Dict[str, int]


class ScraperHealthResponse(BaseModel):
    """Response for scraper health endpoint."""

    status: str
    last_run: Optional[str]
    total_runs: int
    total_scraped: int
    total_skipped: int
    target_year_threshold: int
    blacklisted_years_count: int


# =============================================================================
# SEARCH MODELS
# =============================================================================


class SearchSuggestion(BaseModel):
    """Single search suggestion."""

    text: str
    type: str  # "course_code", "course_name", "subject"
    score: float


class SearchSuggestionsResponse(BaseModel):
    """Response for search suggestions endpoint."""

    suggestions: List[SearchSuggestion]
    query: str
    execution_time_ms: float


# =============================================================================
# STATISTICS MODELS
# =============================================================================


class StatisticsResponse(BaseModel):
    """Response for statistics endpoint."""

    total_papers: int
    papers_by_year: Dict[int, int]
    papers_by_program: Dict[str, int]
    papers_by_program_abbrev: Dict[str, int]
    papers_by_semester: Dict[int, int]
    courses_count: int
    files_loaded: int
