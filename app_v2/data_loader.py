"""Load and aggregate papers from organized JSON files."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import orjson
except ImportError:
    import json as orjson  # type: ignore[no-redef]

logger = logging.getLogger(__name__)


@dataclass
class FileStats:
    """Statistics for a single JSON file."""

    path: str
    papers_count: int
    courses_count: int
    last_modified: str


@dataclass
class LoaderStats:
    """Overall loader statistics."""

    total_papers: int = 0
    unique_urls: int = 0
    files_loaded: int = 0
    last_loaded: Optional[str] = None
    file_stats: Dict[str, FileStats] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class DataLoader:
    """Load organized course-code JSON files with URL deduplication."""

    def __init__(self, data_directory: Path):
        self.data_directory = data_directory
        self.papers: List[Dict[str, Any]] = []
        self.seen_urls: set[str] = set()
        self.stats = LoaderStats()

    def load_all(self) -> List[Dict[str, Any]]:
        """Load all papers from the organized data directory."""
        self.papers = []
        self.seen_urls = set()
        self.stats = LoaderStats()

        if not self.data_directory.exists():
            logger.warning("Data directory not found: %s", self.data_directory.name)
            self.stats.errors.append(
                "Data directory not found: <data directory does not exist>"
            )
            return []

        json_files = list(self.data_directory.rglob("*.json"))
        logger.info(f"Found {len(json_files)} JSON files to load")

        for json_file in json_files:
            self._load_file(json_file)

        self.stats.total_papers = len(self.papers)
        self.stats.unique_urls = len(self.seen_urls)
        self.stats.files_loaded = len(self.stats.file_stats)
        self.stats.last_loaded = datetime.now().isoformat()

        logger.info(
            f"Loaded {self.stats.total_papers} papers "
            f"({self.stats.unique_urls} unique URLs) "
            f"from {self.stats.files_loaded} files"
        )

        return self.papers

    def _read_json_file(self, file_path: Path) -> Dict[str, Any]:
        return orjson.loads(file_path.read_bytes())

    def _add_unique_papers_from_file(
        self, file_path: Path, data: Dict[str, Any]
    ) -> tuple[int, int]:
        paper_count = 0
        course_count = 0
        for course_code, papers_list in data.items():
            if not isinstance(papers_list, list):
                logger.warning(
                    f"Invalid format in {file_path.name}: {course_code} is not a list"
                )
                continue

            course_count += 1
            for paper in papers_list:
                url = paper.get("url")
                if url and url not in self.seen_urls:
                    self.papers.append(paper)
                    self.seen_urls.add(url)
                    paper_count += 1

        return paper_count, course_count

    def _relative_data_path(self, file_path: Path) -> str:
        try:
            return str(file_path.relative_to(self.data_directory))
        except ValueError:
            logger.debug(
                f"Could not determine relative path for {file_path}, using filename only"
            )
            return file_path.name

    def _record_file_stats(
        self, file_path: Path, relative_path: str, paper_count: int, course_count: int
    ) -> None:
        self.stats.file_stats[relative_path] = FileStats(
            path=str(file_path),
            papers_count=paper_count,
            courses_count=course_count,
            last_modified=datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
        )

    def _load_file(self, file_path: Path) -> None:
        try:
            data = self._read_json_file(file_path)
            paper_count, course_count = self._add_unique_papers_from_file(
                file_path, data
            )
            relative_path = self._relative_data_path(file_path)
            self._record_file_stats(file_path, relative_path, paper_count, course_count)
            logger.debug(f"Loaded {paper_count} papers from {relative_path}")
        except orjson.JSONDecodeError as e:
            error_msg = f"Invalid JSON in {file_path.name}: {e.__class__.__name__}"
            logger.error(f"Invalid JSON in {file_path.name}: {e}")
            self.stats.errors.append(error_msg)
        except Exception as e:
            error_msg = f"Error loading {file_path.name}: {e.__class__.__name__}"
            logger.error(f"Error loading {file_path.name}: {e}")
            self.stats.errors.append(error_msg)

    def _get_stats(self) -> Dict[str, Any]:
        """Get statistics about loaded data."""
        return {
            "total_papers": self.stats.total_papers,
            "unique_urls": self.stats.unique_urls,
            "files_loaded": self.stats.files_loaded,
            "last_loaded": self.stats.last_loaded,
            "errors": self.stats.errors,
            "file_stats": {
                path: {
                    "papers": stats.papers_count,
                    "courses": stats.courses_count,
                    "modified": stats.last_modified,
                }
                for path, stats in self.stats.file_stats.items()
            },
        }
