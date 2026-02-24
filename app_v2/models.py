"""
Pydantic Models for Library Portal API V2

Clean, simplified models for request/response handling.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "CurriculumContext",
    "Paper",
    "PaginationInfo",
    "PapersResponse",
    "MetadataResponse",
    "CourseResponse",
    "ComponentHealth",
    "HealthResponse",
    "DataHealthResponse",
    "ScraperHealthResponse",
    "StatisticsResponse",
]

# =============================================================================
# PAPER MODELS
# =============================================================================


def _default_streams_factory() -> List[str]:
    """Default factory for valid_for_streams."""
    return ["all"]


class CurriculumContext(BaseModel):
    """
    Curriculum context indicating which students a paper is relevant for.

    Attributes:
        curriculum_id: Identifier for the curriculum version.
        valid_for_streams: List of streams this paper is valid for (e.g. ["cs", "is"]).
        valid_for_batches: List of batch years this paper is valid for.
        valid_for_branches: List of branches (abbreviations) this paper applies to.
    """

    curriculum_id: Optional[str] = None
    valid_for_streams: List[str] = Field(default_factory=_default_streams_factory)
    valid_for_batches: List[int] = Field(default_factory=list)
    valid_for_branches: Optional[List[str]] = None


class Paper(BaseModel):
    """
    Single question paper with metadata.

    Attributes:
        file_name: Name of the file.
        url: URL to download the paper.
        path: Internal path (deprecated).
        display_title: Formatted title for display.
        year: Academic year (e.g. 2023).
        semester: Semester number (1-8).
        session: Exam session (e.g. "Even (May/Jun)").
        paper_type: Type of paper (e.g. "Regular", "Makeup").
        course_code: Course code (e.g. "UCS123").
        course_name: Name of the course.
        subject_code: Legacy subject code.
        subject_name: Legacy subject name.
        program: Program name.
        program_abbrev: Program abbreviation.
        program_name: Full program name.
        degree_type: Degree type (B.Tech, M.Tech).
        program_category: Category of program.
        specialization: Specialization within program.
        college: College name.
        curriculum_context: Context for curriculum relevance.
        streams: List of relevant streams.
        scraped_at: Timestamp when the paper was scraped.
    """

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

    model_config = ConfigDict(extra="allow")


# =============================================================================
# PAGINATION MODELS
# =============================================================================


class PaginationInfo(BaseModel):
    """
    Pagination metadata included in list responses.

    Attributes:
        total: Total number of items available.
        limit: Max items per page.
        offset: Number of items skipped.
        page: Current page number (1-based).
        total_pages: Total number of pages.
        has_next: Whether there is a next page.
        has_prev: Whether there is a previous page.
    """

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
    """
    Response model for paper listing endpoints.

    Attributes:
        papers: List of paper objects.
        total: Total number of papers matching the filter.
        limit: Pagination limit used.
        offset: Pagination offset used.
        pagination: detailed pagination info.
        execution_time_ms: Time taken to process the request (ms).
    """

    papers: List[Paper]
    total: int
    limit: int
    offset: int
    pagination: PaginationInfo
    execution_time_ms: Optional[float] = None


class MetadataResponse(BaseModel):
    """
    Response model for metadata (filters) endpoint.

    Attributes:
        years: List of available academic years.
        programs: List of available programs.
        program_abbrevs: List of program abbreviations.
        semesters: List of available semesters.
        paper_types: List of paper types.
        degree_types: List of degree types.
        course_codes: List of unique course codes.
        streams: List of streams.
        total_papers: Total count of indexed papers.
    """

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
    """
    Response model for single course details.

    Attributes:
        course_code: The course code requested.
        course_name: Name of the course.
        papers: List of papers for this course.
        total_papers: Count of papers.
    """

    course_code: str
    course_name: Optional[str]
    papers: List[Paper]
    total_papers: int


# =============================================================================
# HEALTH MODELS
# =============================================================================


class ComponentHealth(BaseModel):
    """
    Health status of a single system component.

    Attributes:
        status: Component status (healthy, degraded, unhealthy).
        message: Descriptive message.
        details: Additional component-specific details.
    """

    status: str  # "healthy", "degraded", "unhealthy"
    message: str
    details: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """
    Response model for system health check.

    Attributes:
        status: Overall system status.
        timestamp: Current server time.
        version: API version.
        uptime_seconds: Server uptime in seconds.
        components: Health status of individual components.
    """

    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: str
    version: str
    uptime_seconds: float
    components: Dict[str, ComponentHealth]


class DataHealthResponse(BaseModel):
    """
    Response model for data integrity check.

    Attributes:
        status: Data health status.
        total_papers: Total papers loaded.
        unique_urls: Count of unique paper URLs.
        files_loaded: Number of source JSON files loaded.
        courses_count: Number of courses recognized.
        last_loaded: Timestamp of last data load.
        errors: List of data loading errors.
        papers_by_year: Distribution of papers by year.
        papers_by_program: Distribution of papers by program.
    """

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
    """
    Response model for scraper status.

    Attributes:
        status: Scraper health status.
        last_run: Timestamp of last scraper run.
        total_runs: Total execution count.
        total_scraped: Total URLs scraped.
        total_skipped: Total URLs skipped.
        target_year_threshold: Configured year threshold.
        blacklisted_years_count: Count of years explicitly ignored.
    """

    status: str
    last_run: Optional[str]
    total_runs: int
    total_scraped: int
    total_skipped: int
    target_year_threshold: int
    blacklisted_years_count: int


# =============================================================================
# STATISTICS MODELS
# =============================================================================


class StatisticsResponse(BaseModel):
    """
    Response model for global statistics.

    Attributes:
        total_papers: Total papers in the system.
        papers_by_year: Count per year.
        papers_by_program: Count per program.
        papers_by_program_abbrev: Count per program abbreviation.
        papers_by_semester: Count per semester.
        courses_count: Total unique courses.
        files_loaded: Total source files.
    """

    total_papers: int
    papers_by_year: Dict[int, int]
    papers_by_program: Dict[str, int]
    papers_by_program_abbrev: Dict[str, int]
    papers_by_semester: Dict[int, int]
    courses_count: int
    files_loaded: int
