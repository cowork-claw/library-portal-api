"""Typed FastAPI query parameter aliases for paper routes."""

from typing import Annotated, Literal, Optional

from fastapi import Query

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
