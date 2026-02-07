"""
Paper Indexing Service for Library Portal API V2

Pre-builds indexes for fast filtering and lookup.
"""

import logging
from collections import defaultdict
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from ..data_loader import DataLoader

logger = logging.getLogger(__name__)


class PaperIndex:
    """
    In-memory paper index for fast lookups.

    Pre-builds various indexes on load for efficient filtering:
    - By year
    - By semester
    - By course code
    - By program
    - By stream
    """

    def __init__(self):
        self.papers: List[Dict[str, Any]] = []
        self.loader: Optional[DataLoader] = None

        # Main lookup table
        self._by_url: Dict[str, Dict] = {}

        # Indexes for fast lookup (storing URLs instead of full objects)
        self._by_year: Dict[int, Set[str]] = defaultdict(set)
        self._by_semester: Dict[int, Set[str]] = defaultdict(set)
        self._by_course: Dict[str, Set[str]] = defaultdict(set)
        self._by_program: Dict[str, Set[str]] = defaultdict(set)
        self._by_stream: Dict[str, Set[str]] = defaultdict(set)
        self._by_paper_type: Dict[str, Set[str]] = defaultdict(set)
        self._by_degree_type: Dict[str, Set[str]] = defaultdict(set)

        # Unique values for metadata
        self._unique_years: Set[int] = set()
        self._unique_semesters: Set[int] = set()
        self._unique_course_codes: Set[str] = set()
        self._unique_programs: Set[str] = set()
        self._unique_program_abbrevs: Set[str] = set()
        self._unique_paper_types: Set[str] = set()
        self._unique_degree_types: Set[str] = set()
        self._unique_streams: Set[str] = set()

        # Count aggregations
        self._count_by_year: Dict[int, int] = {}
        self._count_by_semester: Dict[int, int] = {}
        self._count_by_program: Dict[str, int] = {}
        self._count_by_program_abbrev: Dict[str, int] = {}

        # Cached sorted properties
        self._cached_unique_years: Optional[Tuple[int, ...]] = None
        self._cached_unique_semesters: Optional[Tuple[int, ...]] = None
        self._cached_unique_course_codes: Optional[Tuple[str, ...]] = None
        self._cached_unique_programs: Optional[Tuple[str, ...]] = None
        self._cached_unique_program_abbrevs: Optional[Tuple[str, ...]] = None
        self._cached_unique_paper_types: Optional[Tuple[str, ...]] = None
        self._cached_unique_degree_types: Optional[Tuple[str, ...]] = None
        self._cached_unique_streams: Optional[Tuple[str, ...]] = None
        self._cached_count_by_year: Optional[Mapping[int, int]] = None
        self._cached_count_by_semester: Optional[Mapping[int, int]] = None
        self._cached_count_by_program: Optional[Mapping[str, int]] = None
        self._cached_count_by_program_abbrev: Optional[Mapping[str, int]] = None

        # Stats
        self._files_loaded: int = 0

    def load_from_directory(self, loader: DataLoader) -> None:
        """Load papers from data loader and build indexes."""
        self.loader = loader
        self.papers = loader.load_all()
        self._build_indexes()

        stats = loader.get_stats()
        self._files_loaded = stats.get("files_loaded", 0)

        logger.info(f"Indexed {len(self.papers)} papers")

    def _build_indexes(self) -> None:
        """Build all indexes from loaded papers."""
        # Clear existing indexes and data
        self._by_url.clear()
        self._by_year.clear()
        self._by_semester.clear()
        self._by_course.clear()
        self._by_program.clear()
        self._by_stream.clear()
        self._by_paper_type.clear()
        self._by_degree_type.clear()

        self._unique_years.clear()
        self._unique_semesters.clear()
        self._unique_course_codes.clear()
        self._unique_programs.clear()
        self._unique_program_abbrevs.clear()
        self._unique_paper_types.clear()
        self._unique_degree_types.clear()
        self._unique_streams.clear()

        # Reset count aggregations
        self._count_by_year = defaultdict(int)
        self._count_by_semester = defaultdict(int)
        self._count_by_program = defaultdict(int)
        self._count_by_program_abbrev = defaultdict(int)

        # Build indexes and aggregations in a single pass
        for paper in self.papers:
            url = paper.get("url")
            if not url:
                continue

            # Main URL to paper mapping
            self._by_url[url] = paper

            # Year index
            year = paper.get("year")
            if year:
                self._by_year[year].add(url)
                self._unique_years.add(year)
                self._count_by_year[year] += 1

            # Semester index
            semester = paper.get("semester")
            if semester:
                self._by_semester[semester].add(url)
                self._unique_semesters.add(semester)
                self._count_by_semester[semester] += 1

            # Course index
            course_code = paper.get("course_code")
            if course_code:
                self._by_course[course_code].add(url)
                self._unique_course_codes.add(course_code)

            # Program index
            program = paper.get("degree_type") or paper.get("program")
            if program:
                self._by_program[program].add(url)
                self._unique_programs.add(program)
                self._count_by_program[program] += 1

            # Program abbreviation index
            program_abbrev = paper.get("program_abbrev")
            if program_abbrev:
                self._unique_program_abbrevs.add(program_abbrev)
                self._count_by_program_abbrev[program_abbrev] += 1

            # Paper type index
            paper_type = paper.get("paper_type")
            if paper_type:
                self._unique_paper_types.add(paper_type)
                self._by_paper_type[paper_type].add(url)

            # Degree type index
            degree_type = paper.get("degree_type")
            if degree_type:
                self._unique_degree_types.add(degree_type)
                self._by_degree_type[degree_type].add(url)

            # Stream index
            streams = paper.get("streams") or []
            for stream in streams:
                self._by_stream[stream].add(url)
                self._unique_streams.add(stream)

        # Pre-sort and cache properties
        # Use tuples for immutable sequence caching
        self._cached_unique_years = tuple(sorted(self._unique_years, reverse=True))
        self._cached_unique_semesters = tuple(sorted(self._unique_semesters))
        self._cached_unique_course_codes = tuple(sorted(self._unique_course_codes))
        self._cached_unique_programs = tuple(sorted(self._unique_programs))
        self._cached_unique_program_abbrevs = tuple(
            sorted(self._unique_program_abbrevs)
        )
        self._cached_unique_paper_types = tuple(sorted(self._unique_paper_types))
        self._cached_unique_degree_types = tuple(sorted(self._unique_degree_types))
        self._cached_unique_streams = tuple(sorted(self._unique_streams))

        # Use MappingProxyType for immutable dictionary caching
        self._cached_count_by_year = MappingProxyType(
            dict(sorted(self._count_by_year.items(), reverse=True))
        )
        self._cached_count_by_semester = MappingProxyType(
            dict(sorted(self._count_by_semester.items()))
        )
        self._cached_count_by_program = MappingProxyType(
            dict(
                sorted(self._count_by_program.items(), key=lambda x: x[1], reverse=True)
            )
        )
        self._cached_count_by_program_abbrev = MappingProxyType(
            dict(
                sorted(
                    self._count_by_program_abbrev.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )
            )
        )

        logger.debug(
            f"Built indexes: {len(self._unique_years)} years, "
            f"{len(self._unique_course_codes)} courses, "
            f"{len(self._unique_programs)} programs, "
            f"{len(self._unique_streams)} streams"
        )

    # ==========================================================================
    # LOOKUP METHODS
    # ==========================================================================
    def get_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Get a single paper by its URL."""
        return self._by_url.get(url)

    def get_by_urls(self, urls: Set[str]) -> List[Dict[str, Any]]:
        """Get multiple papers from a set of URLs."""
        return [self._by_url[url] for url in urls if url in self._by_url]

    def get_urls_by_year(self, year: int) -> Set[str]:
        """Get paper URLs for a specific year."""
        return self._by_year.get(year, set())

    def get_urls_by_semester(self, semester: int) -> Set[str]:
        """Get paper URLs for a specific semester."""
        return self._by_semester.get(semester, set())

    def get_urls_by_course(self, course_code: str) -> Set[str]:
        """Get paper URLs for a specific course code."""
        return self._by_course.get(course_code.upper(), set())

    def get_papers_by_course(self, course_code: str) -> List[Dict[str, Any]]:
        """Get papers for a specific course code."""
        urls = self.get_urls_by_course(course_code)
        return self.get_by_urls(urls)

    def get_urls_by_program(self, program: str) -> Set[str]:
        """Get paper URLs for a specific program."""
        return self._by_program.get(program, set())

    def get_urls_by_stream(self, stream: str) -> Set[str]:
        """Get paper URLs for a specific stream."""
        return self._by_stream.get(stream, set())

    def get_urls_by_paper_type(self, paper_type: str) -> Set[str]:
        """Get paper URLs for a specific paper type."""
        return self._by_paper_type.get(paper_type, set())

    def get_urls_by_degree_type(self, degree_type: str) -> Set[str]:
        """Get paper URLs for a specific degree type."""
        return self._by_degree_type.get(degree_type, set())

    # ==========================================================================
    # PROPERTY ACCESSORS
    # ==========================================================================

    @property
    def total_papers(self) -> int:
        return len(self.papers)

    @property
    def files_loaded(self) -> int:
        return self._files_loaded

    @property
    def unique_years(self) -> List[int]:
        return self._cached_unique_years or ()

    @property
    def unique_semesters(self) -> List[int]:
        return self._cached_unique_semesters or ()

    @property
    def unique_course_codes(self) -> List[str]:
        return self._cached_unique_course_codes or ()

    @property
    def unique_programs(self) -> List[str]:
        return self._cached_unique_programs or ()

    @property
    def unique_program_abbrevs(self) -> List[str]:
        return self._cached_unique_program_abbrevs or ()

    @property
    def unique_paper_types(self) -> List[str]:
        return self._cached_unique_paper_types or ()

    @property
    def unique_degree_types(self) -> List[str]:
        return self._cached_unique_degree_types or ()

    @property
    def unique_streams(self) -> List[str]:
        return self._cached_unique_streams or ()

    @property
    def count_by_year(self) -> Dict[int, int]:
        return self._cached_count_by_year or {}

    @property
    def count_by_semester(self) -> Dict[int, int]:
        return self._cached_count_by_semester or {}

    @property
    def count_by_program(self) -> Dict[str, int]:
        return self._cached_count_by_program or {}

    @property
    def count_by_program_abbrev(self) -> Dict[str, int]:
        return self._cached_count_by_program_abbrev or {}


# Global paper index instance
paper_index = PaperIndex()
