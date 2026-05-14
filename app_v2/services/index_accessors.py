"""Lookup and read-only accessor methods for the paper index."""

from functools import lru_cache
from types import MappingProxyType
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from .search import _search_papers

SEARCH_CACHE_MAXSIZE = 32


class PaperIndexAccessors:
    """Mixin containing PaperIndex lookup methods and immutable properties."""

    @lru_cache(maxsize=SEARCH_CACHE_MAXSIZE)
    def _search_cached(self, normalized_query: str) -> Tuple[str, ...]:
        results = _search_papers(self.papers, normalized_query)
        return tuple(url for paper in results if (url := paper.get("url")))

    def _search(self, query: str) -> List[str]:
        """Search all papers and return matching URLs sorted by relevance."""
        normalized_query = query.strip().lower()
        if not normalized_query:
            return []
        return list(self._search_cached(normalized_query))

    def _get_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        return self._by_url.get(url)

    def _get_by_urls(self, urls: Iterable[str]) -> List[Dict[str, Any]]:
        """Get multiple papers from a set of URLs."""
        return [self._by_url[url] for url in urls if url in self._by_url]

    def _get_urls_by_year(self, year: int) -> Set[str]:
        """Get paper URLs for a specific year."""
        return self._by_year.get(year, set())

    def _get_urls_by_semester(self, semester: int) -> Set[str]:
        """Get paper URLs for a specific semester."""
        return self._by_semester.get(semester, set())

    def _get_urls_by_course(self, course_code: str) -> Set[str]:
        """Get paper URLs for a specific course code."""
        return self._by_course.get(course_code.upper(), set())

    def _get_papers_by_course(self, course_code: str) -> List[Dict[str, Any]]:
        urls = self._get_urls_by_course(course_code)
        return self._get_by_urls(urls)

    def _get_urls_by_program(self, program: str) -> Set[str]:
        return self._by_program.get(program, set())

    def _get_urls_by_stream(self, stream: str) -> Set[str]:
        return self._by_stream.get(stream, set())

    def _get_urls_by_paper_type(self, paper_type: str) -> Set[str]:
        return self._by_paper_type.get(paper_type, set())

    def _get_urls_by_degree_type(self, degree_type: str) -> Set[str]:
        return self._by_degree_type.get(degree_type, set())

    def _get_urls_by_program_abbrev(self, program_abbrev: str) -> Set[str]:
        return self._by_program_abbrev.get(program_abbrev.upper(), set())

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
