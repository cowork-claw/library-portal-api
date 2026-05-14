from functools import lru_cache
from types import MappingProxyType
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from .search import _search_papers

SEARCH_CACHE_MAXSIZE = 32


class PaperIndexAccessors:
    @lru_cache(maxsize=SEARCH_CACHE_MAXSIZE)
    def _search_cached(self, normalized_query: str) -> Tuple[str, ...]:
        results = _search_papers(self.papers, normalized_query)
        return tuple(url for paper in results if (url := paper.get("url")))

    def _search(self, query: str) -> List[str]:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return []
        return list(self._search_cached(normalized_query))

    def _get_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        return self._by_url.get(url)

    def _get_by_urls(self, urls: Iterable[str]) -> List[Dict[str, Any]]:
        return [self._by_url[url] for url in urls if url in self._by_url]

    def _get_urls_by_year(self, year: int) -> Set[str]:
        return self._by_year.get(year, set())

    def _get_urls_by_semester(self, semester: int) -> Set[str]:
        return self._by_semester.get(semester, set())

    def _get_urls_by_course(self, course_code: str) -> Set[str]:
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
    def _paper_count(self) -> int:
        return len(self.papers)

    @property
    def _loaded_file_count(self) -> int:
        return self._files_loaded

    @property
    def _unique_year_values(self) -> Tuple[int, ...]:
        return self._cached_unique_years or ()

    @property
    def _unique_semester_values(self) -> Tuple[int, ...]:
        return self._cached_unique_semesters or ()

    @property
    def _unique_course_code_values(self) -> Tuple[str, ...]:
        return self._cached_unique_course_codes or ()

    @property
    def _unique_program_values(self) -> Tuple[str, ...]:
        return self._cached_unique_programs or ()

    @property
    def _unique_program_abbrev_values(self) -> Tuple[str, ...]:
        return self._cached_unique_program_abbrevs or ()

    @property
    def _unique_paper_type_values(self) -> Tuple[str, ...]:
        return self._cached_unique_paper_types or ()

    @property
    def _unique_degree_type_values(self) -> Tuple[str, ...]:
        return self._cached_unique_degree_types or ()

    @property
    def _unique_stream_values(self) -> Tuple[str, ...]:
        return self._cached_unique_streams or ()

    @property
    def _count_by_year_values(self) -> Mapping[int, int]:
        return self._cached_count_by_year or MappingProxyType({})

    @property
    def _count_by_semester_values(self) -> Mapping[int, int]:
        return self._cached_count_by_semester or MappingProxyType({})

    @property
    def _count_by_program_values(self) -> Mapping[str, int]:
        return self._cached_count_by_program or MappingProxyType({})

    @property
    def _count_by_program_abbrev_values(self) -> Mapping[str, int]:
        return self._cached_count_by_program_abbrev or MappingProxyType({})
