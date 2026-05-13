"""
Paper Indexing Service for Library Portal API V2

Pre-builds indexes for fast filtering and lookup.
"""

import logging
from collections import defaultdict
from functools import lru_cache
from threading import RLock
from types import MappingProxyType
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from app_v2.utils import WORD_TOKEN_PATTERN

from ..data_loader import DataLoader
from .search import search_papers

logger = logging.getLogger(__name__)

__all__ = ["PaperIndex", "paper_index"]
SEARCH_CACHE_MAXSIZE = 32
SEARCH_META_FIELDS = (
    "course_code",
    "course_name",
    "subject_name",
    "display_title",
    "file_name",
)


def build_search_meta(
    paper: Dict[str, Any], field_meta_cache: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, Dict[str, Any]]:
    """Build normalized search metadata for a paper, optionally using Flyweight reuse."""
    search_meta: Dict[str, Dict[str, Any]] = {}
    for field in SEARCH_META_FIELDS:
        if (val := paper.get(field)) and (val_lower := str(val).lower()):
            if field_meta_cache is None:
                search_meta[field] = {
                    "lower": val_lower,
                    "words": set(WORD_TOKEN_PATTERN.findall(val_lower)),
                }
                continue

            if val_lower not in field_meta_cache:
                field_meta_cache[val_lower] = {
                    "lower": val_lower,
                    "words": set(WORD_TOKEN_PATTERN.findall(val_lower)),
                }
            search_meta[field] = field_meta_cache[val_lower]
    return search_meta


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
        self._swap_lock = RLock()
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
        self._by_program_abbrev: Dict[str, Set[str]] = defaultdict(set)

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

        # Clear loader data to free memory (data is now in self.papers)
        # Note: We must reassign to new empty structures rather than clearing the existing objects,
        # because self.papers might reference the same list object returned by load_all().
        loader.papers = []
        loader.seen_urls = set()

        # Clear search cache on reload
        self._search_cached.cache_clear()

        logger.info(f"Indexed {len(self.papers)} papers")

    def reload_from_directory(self, loader: DataLoader) -> None:
        """Build a replacement index first, then publish it."""
        new_index = PaperIndex()
        new_index.load_from_directory(loader)
        if new_index.loader and new_index.loader.stats.errors:
            raise RuntimeError("Data reload failed; keeping previous index")
        self.replace_with(new_index)

    def replace_with(self, other: "PaperIndex") -> None:
        """Replace this index's state with a fully built index."""
        with self._swap_lock:
            swap_lock = self._swap_lock
            new_state = {
                key: value
                for key, value in other.__dict__.items()
                if key != "_swap_lock"
            }
            self.__dict__.update(new_state)
            self._swap_lock = swap_lock

    def _clear_indexes(self) -> None:
        """Clear existing indexes and data."""
        self._by_url.clear()
        self._by_year.clear()
        self._by_semester.clear()
        self._by_course.clear()
        self._by_program.clear()
        self._by_stream.clear()
        self._by_paper_type.clear()
        self._by_degree_type.clear()
        self._by_program_abbrev.clear()

        self._unique_years.clear()
        self._unique_semesters.clear()
        self._unique_course_codes.clear()
        self._unique_programs.clear()
        self._unique_program_abbrevs.clear()
        self._unique_paper_types.clear()
        self._unique_degree_types.clear()
        self._unique_streams.clear()

    def _build_indexes(self) -> None:
        """Build all indexes from loaded papers."""
        self._clear_indexes()

        # Reset count aggregations
        self._count_by_year = defaultdict(int)
        self._count_by_semester = defaultdict(int)
        self._count_by_program = defaultdict(int)
        self._count_by_program_abbrev = defaultdict(int)

        field_meta_cache: Dict[str, Dict[str, Any]] = (
            {}
        )  # Flyweight cache for search metadata

        # Build indexes and aggregations in a single pass
        for paper in self.papers:
            self._index_paper(paper, field_meta_cache)

        self._finalize_indexes()

    def _add_index_value(
        self,
        index: Dict[Any, Set[str]],
        unique_values: Set[Any],
        url: str,
        value: Any,
        counts: Dict[Any, int] | None = None,
    ) -> None:
        """Add one scalar value to an index, unique set, and optional count map."""
        if not value:
            return
        index[value].add(url)
        unique_values.add(value)
        if counts is not None:
            counts[value] += 1

    def _index_streams(self, url: str, streams: Iterable[str]) -> None:
        """Index stream membership for a paper URL."""
        for stream in streams:
            self._by_stream[stream].add(url)
            self._unique_streams.add(stream)

    def _index_program_abbrev(self, url: str, program_abbrev: Any) -> None:
        """Index a normalized program abbreviation for a paper URL."""
        if not program_abbrev:
            return
        self._add_index_value(
            self._by_program_abbrev,
            self._unique_program_abbrevs,
            url,
            program_abbrev.upper(),
            self._count_by_program_abbrev,
        )

    def _index_paper(
        self, paper: Dict[str, Any], field_meta_cache: Dict[str, Any]
    ) -> None:
        """Index a single paper and build aggregations."""
        url = paper.get("url")
        if not url:
            return

        self._by_url[url] = paper
        self._add_index_value(
            self._by_year,
            self._unique_years,
            url,
            paper.get("year"),
            self._count_by_year,
        )
        self._add_index_value(
            self._by_semester,
            self._unique_semesters,
            url,
            paper.get("semester"),
            self._count_by_semester,
        )
        self._add_index_value(
            self._by_course, self._unique_course_codes, url, paper.get("course_code")
        )
        self._add_index_value(
            self._by_program,
            self._unique_programs,
            url,
            paper.get("degree_type") or paper.get("program"),
            self._count_by_program,
        )

        self._index_program_abbrev(url, paper.get("program_abbrev"))

        self._add_index_value(
            self._by_paper_type, self._unique_paper_types, url, paper.get("paper_type")
        )
        self._add_index_value(
            self._by_degree_type,
            self._unique_degree_types,
            url,
            paper.get("degree_type"),
        )
        self._index_streams(url, paper.get("streams") or [])

        self._compute_search_meta(paper, field_meta_cache)

    def _compute_search_meta(
        self, paper: Dict[str, Any], field_meta_cache: Dict[str, Any]
    ) -> None:
        """Pre-compute and cache search metadata for a paper."""
        paper["_search_meta"] = build_search_meta(paper, field_meta_cache)

    def _finalize_indexes(self) -> None:
        """Pre-sort and cache properties after index construction."""
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
        self._cached_count_by_year = self._sort_and_proxy(
            self._count_by_year, reverse=True
        )
        self._cached_count_by_semester = self._sort_and_proxy(self._count_by_semester)
        self._cached_count_by_program = self._sort_and_proxy(
            self._count_by_program, key=lambda x: x[1], reverse=True
        )
        self._cached_count_by_program_abbrev = self._sort_and_proxy(
            self._count_by_program_abbrev, key=lambda x: x[1], reverse=True
        )

        logger.debug(
            f"Built indexes: {len(self._unique_years)} years, "
            f"{len(self._unique_course_codes)} courses, "
            f"{len(self._unique_programs)} programs, "
            f"{len(self._unique_streams)} streams"
        )

    def _sort_and_proxy(self, data: Dict, key=None, reverse=False) -> MappingProxyType:
        """Helper to sort a dictionary and return an immutable proxy."""
        return MappingProxyType(dict(sorted(data.items(), key=key, reverse=reverse)))

    # ==========================================================================
    # LOOKUP METHODS
    # ==========================================================================
    @lru_cache(maxsize=SEARCH_CACHE_MAXSIZE)
    def _search_cached(self, normalized_query: str) -> Tuple[str, ...]:
        """Return cached matching URLs for a normalized query."""
        results = search_papers(self.papers, normalized_query)
        return tuple(url for paper in results if (url := paper.get("url")))

    def search(self, query: str) -> List[str]:
        """Search all papers and return matching URLs sorted by relevance."""
        normalized_query = query.strip().lower()
        if not normalized_query:
            return []
        return list(self._search_cached(normalized_query))

    def get_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Get a single paper by its URL, or None if not found."""
        return self._by_url.get(url)

    def get_by_urls(self, urls: Iterable[str]) -> List[Dict[str, Any]]:
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

    def get_urls_by_program_abbrev(self, program_abbrev: str) -> Set[str]:
        """Get paper URLs for a specific program abbreviation (case-insensitive)."""
        return self._by_program_abbrev.get(program_abbrev.upper(), set())

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
    def unique_years(self) -> Tuple[int, ...]:
        return self._cached_unique_years or ()

    @property
    def unique_semesters(self) -> Tuple[int, ...]:
        return self._cached_unique_semesters or ()

    @property
    def unique_course_codes(self) -> Tuple[str, ...]:
        return self._cached_unique_course_codes or ()

    @property
    def unique_programs(self) -> Tuple[str, ...]:
        return self._cached_unique_programs or ()

    @property
    def unique_program_abbrevs(self) -> Tuple[str, ...]:
        return self._cached_unique_program_abbrevs or ()

    @property
    def unique_paper_types(self) -> Tuple[str, ...]:
        return self._cached_unique_paper_types or ()

    @property
    def unique_degree_types(self) -> Tuple[str, ...]:
        return self._cached_unique_degree_types or ()

    @property
    def unique_streams(self) -> Tuple[str, ...]:
        return self._cached_unique_streams or ()

    @property
    def count_by_year(self) -> Mapping[int, int]:
        return self._cached_count_by_year or MappingProxyType({})

    @property
    def count_by_semester(self) -> Mapping[int, int]:
        return self._cached_count_by_semester or MappingProxyType({})

    @property
    def count_by_program(self) -> Mapping[str, int]:
        return self._cached_count_by_program or MappingProxyType({})

    @property
    def count_by_program_abbrev(self) -> Mapping[str, int]:
        return self._cached_count_by_program_abbrev or MappingProxyType({})


# Global paper index instance
paper_index = PaperIndex()
