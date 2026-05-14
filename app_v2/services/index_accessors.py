import re
from functools import lru_cache
from types import MappingProxyType
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from thefuzz import fuzz

SEARCH_CACHE_MAXSIZE = 32
WORD_MATCH_SCORE_FACTOR = 0.7
WORD_TOKEN_PATTERN = re.compile(r"\w+")
SEARCH_FIELDS = [
    ("course_code", 1.0),
    ("course_name", 0.9),
    ("subject_name", 0.9),
    ("display_title", 0.7),
    ("file_name", 0.5),
]


def _tokenize_words(text: str) -> Set[str]:
    return set(WORD_TOKEN_PATTERN.findall(text))


def _search_papers(
    papers: List[Dict[str, Any]], query: str, threshold: float = 0.5
) -> List[Dict[str, Any]]:
    if not query or not papers:
        return papers

    query = query.strip().lower()
    if not query:
        return papers
    query_words = _tokenize_words(query)
    effective_threshold = max(threshold, 0.01) if threshold <= 0 else threshold

    results = [
        (paper, score)
        for paper in papers
        if (score := _calculate_relevance(paper, query, query_words))
        >= effective_threshold
    ]
    results.sort(key=lambda x: x[1], reverse=True)
    return [paper for paper, score in results]


def _field_search_data(
    paper: Dict[str, Any], search_meta: Optional[Dict[str, Any]], field_name: str
) -> Optional[tuple[str, Optional[Set[str]]]]:
    if search_meta and (meta := search_meta.get(field_name)):
        return meta["lower"], meta["words"]

    value = paper.get(field_name)
    if not value:
        return None
    return str(value).lower(), None


def _exact_or_contains_score(
    query: str, value_lower: str, weight: float
) -> Optional[float]:
    if query == value_lower:
        return weight
    if query not in value_lower:
        return None
    return (0.95 if value_lower.startswith(query) else 0.8) * weight


def _fuzzy_score(query: str, value_lower: str, weight: float) -> float:
    ratio = fuzz.WRatio(query, value_lower) / 100.0
    if ratio > WORD_MATCH_SCORE_FACTOR:
        return ratio * weight
    return 0.0


def _word_overlap_score(
    query_words: Set[str],
    value_words: Optional[Set[str]],
    value_lower: str,
    weight: float,
) -> float:
    if not query_words:
        return 0.0

    if value_words is None:
        value_words = _tokenize_words(value_lower)

    matching_words = query_words & value_words
    if not matching_words:
        return 0.0
    return (len(matching_words) / len(query_words)) * WORD_MATCH_SCORE_FACTOR * weight


def _calculate_relevance(
    paper: Dict[str, Any], query: str, query_words: Set[str]
) -> float:
    max_score = 0.0
    search_meta = paper.get("_search_meta")

    for field_name, weight in SEARCH_FIELDS:
        if max_score >= weight:
            break

        field_data = _field_search_data(paper, search_meta, field_name)
        if field_data is None:
            continue

        value_lower, value_words = field_data
        phrase_score = _exact_or_contains_score(query, value_lower, weight)
        if phrase_score is not None:
            if phrase_score == weight:
                return phrase_score
            max_score = max(max_score, phrase_score)
            continue

        max_score = max(max_score, _fuzzy_score(query, value_lower, weight))
        if max_score >= WORD_MATCH_SCORE_FACTOR * weight:
            continue

        max_score = max(
            max_score,
            _word_overlap_score(query_words, value_words, value_lower, weight),
        )

    return max_score


class PaperIndexAccessors:
    @lru_cache(maxsize=SEARCH_CACHE_MAXSIZE)
    def _search_cached(self, normalized_query: str) -> Tuple[str, ...]:
        results = _search_papers(self.papers, normalized_query)
        return tuple(url for paper in results if (url := paper.get("url")))

    def _search(self, query: str) -> List[str]:
        normalized_query = query.strip().lower()
        return list(self._search_cached(normalized_query)) if normalized_query else []

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
        return self._get_by_urls(self._get_urls_by_course(course_code))

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
