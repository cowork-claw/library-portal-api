"""
Paper Indexing Service for Library Portal API V2

Pre-builds indexes for fast filtering and lookup.
"""

import logging
from typing import Dict, List, Any, Optional, Set
from collections import defaultdict

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

        # Unique values for metadata
        self._unique_years: Set[int] = set()
        self._unique_semesters: Set[int] = set()
        self._unique_course_codes: Set[str] = set()
        self._unique_programs: Set[str] = set()
        self._unique_streams: Set[str] = set()

        # Count aggregations
        self._count_by_year: Dict[int, int] = {}
        self._count_by_semester: Dict[int, int] = {}
        self._count_by_program: Dict[str, int] = {}

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

        self._unique_years.clear()
        self._unique_semesters.clear()
        self._unique_course_codes.clear()
        self._unique_programs.clear()
        self._unique_streams.clear()

        # Reset count aggregations
        self._count_by_year = defaultdict(int)
        self._count_by_semester = defaultdict(int)
        self._count_by_program = defaultdict(int)

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

            # Stream index
            streams = paper.get("streams") or []
            for stream in streams:
                self._by_stream[stream].add(url)
                self._unique_streams.add(stream)

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

    def get_papers_by_course(self, course_code: str) -> List[Dict[str, Any]]:
        """Get papers for a specific course code."""
        urls = self._by_course.get(course_code.upper(), set())
        return self.get_by_urls(urls)

    def get_urls_by_program(self, program: str) -> Set[str]:
        """Get paper URLs for a specific program."""
        return self._by_program.get(program, set())

    def get_urls_by_stream(self, stream: str) -> Set[str]:
        """Get paper URLs for a specific stream."""
        return self._by_stream.get(stream, set())

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
        return sorted(self._unique_years, reverse=True)

    @property
    def unique_semesters(self) -> List[int]:
        return sorted(self._unique_semesters)

    @property
    def unique_course_codes(self) -> List[str]:
        return sorted(self._unique_course_codes)

    @property
    def unique_programs(self) -> List[str]:
        return sorted(self._unique_programs)

    @property
    def unique_streams(self) -> List[str]:
        return sorted(self._unique_streams)

    @property
    def count_by_year(self) -> Dict[int, int]:
        return dict(sorted(self._count_by_year.items(), reverse=True))

    @property
    def count_by_semester(self) -> Dict[int, int]:
        return dict(sorted(self._count_by_semester.items()))

    @property
    def count_by_program(self) -> Dict[str, int]:
        return dict(
            sorted(self._count_by_program.items(), key=lambda x: x[1], reverse=True)
        )


# Global paper index instance
paper_index = PaperIndex()
