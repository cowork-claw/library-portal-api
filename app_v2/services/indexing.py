import logging
from collections import defaultdict
from collections.abc import Mapping
from threading import RLock
from types import MappingProxyType
from typing import Any

from ..data_loader import DataLoader
from .index_accessors import WORD_TOKEN_PATTERN, PaperIndexAccessors

logger = logging.getLogger(__name__)

SEARCH_META_FIELDS = (
    "course_code",
    "course_name",
    "subject_name",
    "display_title",
    "file_name",
)


def _build_search_meta(
    paper: dict[str, Any], field_meta_cache: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    search_meta: dict[str, dict[str, Any]] = {}
    for field in SEARCH_META_FIELDS:
        if (val := paper.get(field)) and (val_lower := str(val).lower()):
            if val_lower not in field_meta_cache:
                field_meta_cache[val_lower] = {
                    "lower": val_lower,
                    "words": set(WORD_TOKEN_PATTERN.findall(val_lower)),
                }
            search_meta[field] = field_meta_cache[val_lower]
    return search_meta


class PaperIndex(PaperIndexAccessors):
    def __init__(self):
        self._swap_lock = RLock()
        self.papers: list[dict[str, Any]] = []
        self.loader: DataLoader | None = None

        # Main lookup table
        self._by_url: dict[str, dict] = {}

        # Indexes for fast lookup (storing URLs instead of full objects)
        self._by_year: dict[int, set[str]] = defaultdict(set)
        self._by_semester: dict[int, set[str]] = defaultdict(set)
        self._by_course: dict[str, set[str]] = defaultdict(set)
        self._by_program: dict[str, set[str]] = defaultdict(set)
        self._by_stream: dict[str, set[str]] = defaultdict(set)
        self._by_paper_type: dict[str, set[str]] = defaultdict(set)
        self._by_degree_type: dict[str, set[str]] = defaultdict(set)
        self._by_program_abbrev: dict[str, set[str]] = defaultdict(set)

        # Unique values for metadata
        self._unique_years: set[int] = set()
        self._unique_semesters: set[int] = set()
        self._unique_course_codes: set[str] = set()
        self._unique_programs: set[str] = set()
        self._unique_program_abbrevs: set[str] = set()
        self._unique_paper_types: set[str] = set()
        self._unique_degree_types: set[str] = set()
        self._unique_streams: set[str] = set()

        # Count aggregations
        self._count_by_year: dict[int, int] = {}
        self._count_by_semester: dict[int, int] = {}
        self._count_by_program: dict[str, int] = {}
        self._count_by_program_abbrev: dict[str, int] = {}

        # Cached sorted properties
        self._cached_unique_years: tuple[int, ...] | None = None
        self._cached_unique_semesters: tuple[int, ...] | None = None
        self._cached_unique_course_codes: tuple[str, ...] | None = None
        self._cached_unique_programs: tuple[str, ...] | None = None
        self._cached_unique_program_abbrevs: tuple[str, ...] | None = None
        self._cached_unique_paper_types: tuple[str, ...] | None = None
        self._cached_unique_degree_types: tuple[str, ...] | None = None
        self._cached_unique_streams: tuple[str, ...] | None = None
        self._cached_count_by_year: Mapping[int, int] | None = None
        self._cached_count_by_semester: Mapping[int, int] | None = None
        self._cached_count_by_program: Mapping[str, int] | None = None
        self._cached_count_by_program_abbrev: Mapping[str, int] | None = None

        # Stats
        self._files_loaded: int = 0

    def _load_from_directory(self, loader: DataLoader) -> None:
        self.loader = loader
        self.papers = loader._load_all()
        self._build_indexes()

        self._files_loaded = loader.stats.files_loaded

        # Clear loader data to free memory (data is now in self.papers)
        # Note: We must reassign to new empty structures rather than clearing the existing objects,
        # because self.papers might reference the same list object returned by _load_all().
        loader.papers = []
        loader.seen_urls = set()

        # Clear search cache on reload
        self._search_cached.cache_clear()

        logger.info(f"Indexed {len(self.papers)} papers")

    def _reload_from_directory(self, loader: DataLoader) -> None:
        new_index = PaperIndex()
        new_index._load_from_directory(loader)
        if new_index.loader and new_index.loader.stats.errors:
            raise RuntimeError("Data reload failed; keeping previous index")
        self._replace_with(new_index)

    def _replace_with(self, other: "PaperIndex") -> None:
        with self._swap_lock:
            swap_lock = self._swap_lock
            self.__dict__.update(
                {
                    key: value
                    for key, value in other.__dict__.items()
                    if key != "_swap_lock"
                }
            )
            self._swap_lock = swap_lock

    def _clear_indexes(self) -> None:
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
        self._clear_indexes()

        # Reset count aggregations
        self._count_by_year = defaultdict(int)
        self._count_by_semester = defaultdict(int)
        self._count_by_program = defaultdict(int)
        self._count_by_program_abbrev = defaultdict(int)

        field_meta_cache: dict[str, dict[str, Any]] = {}

        # Build indexes and aggregations in a single pass
        for paper in self.papers:
            self._index_paper(paper, field_meta_cache)

        self._finalize_indexes()

    def _add_index_value(
        self,
        index: dict[Any, set[str]],
        unique_values: set[Any],
        url: str,
        value: Any,
        counts: dict[Any, int] | None = None,
    ) -> None:
        if not value:
            return
        index[value].add(url)
        unique_values.add(value)
        if counts is not None:
            counts[value] += 1

    def _index_paper(
        self, paper: dict[str, Any], field_meta_cache: dict[str, Any]
    ) -> None:
        url = paper.get("url")
        if not url:
            return

        self._by_url[url] = paper
        for index, unique_values, value, counts in (
            (self._by_year, self._unique_years, paper.get("year"), self._count_by_year),
            (
                self._by_semester,
                self._unique_semesters,
                paper.get("semester"),
                self._count_by_semester,
            ),
            (
                self._by_course,
                self._unique_course_codes,
                paper.get("course_code"),
                None,
            ),
            (
                self._by_program,
                self._unique_programs,
                paper.get("program"),
                self._count_by_program,
            ),
        ):
            self._add_index_value(index, unique_values, url, value, counts)

        if program_abbrev := paper.get("program_abbrev"):
            self._add_index_value(
                self._by_program_abbrev,
                self._unique_program_abbrevs,
                url,
                program_abbrev.upper(),
                self._count_by_program_abbrev,
            )

        for index, unique_values, value in (
            (self._by_paper_type, self._unique_paper_types, paper.get("paper_type")),
            (self._by_degree_type, self._unique_degree_types, paper.get("degree_type")),
        ):
            self._add_index_value(index, unique_values, url, value)
        for stream in paper.get("streams") or []:
            self._by_stream[stream].add(url)
            self._unique_streams.add(stream)

        paper["_search_meta"] = _build_search_meta(paper, field_meta_cache)

    def _finalize_indexes(self) -> None:
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

    def _sort_and_proxy(self, data: dict, key=None, reverse=False) -> MappingProxyType:
        return MappingProxyType(dict(sorted(data.items(), key=key, reverse=reverse)))


paper_index = PaperIndex()
