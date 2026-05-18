from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CurriculumContext(BaseModel):

    curriculum_id: str | None = None
    valid_for_streams: list[str] = Field(default_factory=lambda: ["all"])
    valid_for_batches: list[int] = Field(default_factory=list)
    valid_for_branches: list[str] | None = None


class Paper(BaseModel):

    # File info
    file_name: str
    url: str | None = None
    path: str | None = None
    display_title: str | None = None

    # Core identification
    year: int | None = None
    semester: int | None = None
    session: str | None = None  # "Even (May/Jun)" or "Odd (Nov/Dec)"
    paper_type: str | None = None  # "Regular", "Supplementary", "Makeup"

    # Course info
    course_code: str | None = None
    course_name: str | None = None
    subject_code: str | None = None  # Backwards compat
    subject_name: str | None = None  # Backwards compat

    # Program info
    program: str | None = None
    program_abbrev: str | None = None
    program_name: str | None = None
    degree_type: str | None = None
    program_category: str | None = None
    specialization: str | None = None
    college: str | None = None

    # Curriculum context (V2)
    curriculum_context: CurriculumContext | None = None
    streams: list[str] | None = None

    # Metadata
    scraped_at: str | None = None

    model_config = ConfigDict(extra="allow")


class PaginationInfo(BaseModel):

    total: int
    limit: int
    offset: int
    page: int
    total_pages: int
    has_next: bool
    has_prev: bool


class PapersResponse(BaseModel):

    papers: list[Paper]
    total: int
    limit: int
    offset: int
    pagination: PaginationInfo
    execution_time_ms: float | None = None


class MetadataResponse(BaseModel):

    years: list[int]
    programs: list[str]
    program_abbrevs: list[str]
    semesters: list[int]
    paper_types: list[str]
    degree_types: list[str]
    course_codes: list[str]
    streams: list[str]
    total_papers: int


class CourseResponse(BaseModel):

    course_code: str
    course_name: str | None
    papers: list[Paper]
    total_papers: int


class ComponentHealth(BaseModel):

    status: str  # "healthy", "degraded", "unhealthy"
    message: str
    details: dict[str, Any] | None = None


class HealthResponse(BaseModel):

    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: str
    version: str
    uptime_seconds: float
    components: dict[str, ComponentHealth]


class DataHealthResponse(BaseModel):

    status: str
    total_papers: int
    unique_urls: int
    files_loaded: int
    courses_count: int
    last_loaded: str | None
    errors: list[str]
    papers_by_year: dict[int, int]
    papers_by_program: dict[str, int]


class ScraperHealthResponse(BaseModel):

    status: str
    last_run: str | None
    total_runs: int
    total_scraped: int
    total_skipped: int
    target_year_threshold: int
    blacklisted_years_count: int


class ReloadResponse(BaseModel):

    reload_id: str
    message: str


class StatisticsResponse(BaseModel):

    total_papers: int
    papers_by_year: dict[int, int]
    papers_by_program: dict[str, int]
    papers_by_program_abbrev: dict[str, int]
    papers_by_semester: dict[int, int]
    courses_count: int
    files_loaded: int
