"""
Multi-file Data Loader for Library Portal V2

Loads and aggregates papers from the organized folder structure:
data/classified/organized/
├── btech/branches/*.json
├── btech/first_year/*.json
├── masters/*.json
├── bsc/*.json
└── other.json
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import orjson

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
    """
    Load and aggregate papers from organized folder structure.

    The data is organized as:
    - Each JSON file contains: {course_code: [paper_objects...]}
    - Papers are deduplicated by URL
    - File metadata is tracked for health checks
    """

    def __init__(self, data_directory: Path):
        self.data_directory = data_directory
        self.papers: List[Dict[str, Any]] = []
        self.papers_by_url: Dict[str, Dict[str, Any]] = {}
        self.stats = LoaderStats()

    def load_all(self) -> List[Dict[str, Any]]:
        """
        Load all papers from organized JSON files.

        Returns:
            List of all paper dictionaries, deduplicated by URL
        """
        self.papers = []
        self.papers_by_url = {}
        self.stats = LoaderStats()

        if not self.data_directory.exists():
            logger.error(f"Data directory not found: {self.data_directory}")
            self.stats.errors.append(f"Data directory not found: {self.data_directory}")
            return []

        json_files = list(self.data_directory.rglob("*.json"))
        logger.info(f"Found {len(json_files)} JSON files to load")

        for json_file in json_files:
            self._load_file(json_file)

        self.stats.total_papers = len(self.papers)
        self.stats.unique_urls = len(self.papers_by_url)
        self.stats.files_loaded = len(self.stats.file_stats)
        self.stats.last_loaded = datetime.now().isoformat()

        logger.info(
            f"Loaded {self.stats.total_papers} papers "
            f"({self.stats.unique_urls} unique URLs) "
            f"from {self.stats.files_loaded} files"
        )

        return self.papers

    def _load_file(self, file_path: Path) -> None:
        """Load papers from a single JSON file."""
        try:
            with open(file_path, "rb") as f:
                data = orjson.loads(f.read())

            # Papers added from this file (might be duplicates of papers in other files)
            # but we track how many we *processed* from this file that were unique so far.
            paper_count = 0
            course_count = 0

            # Data format: {course_code: [papers...]}
            for course_code, papers_list in data.items():
                if not isinstance(papers_list, list):
                    logger.warning(
                        f"Invalid format in {file_path.name}: {course_code} is not a list"
                    )
                    continue

                course_count += 1

                for paper in papers_list:
                    # Deduplicate by URL
                    url = paper.get("url")
                    if url and url not in self.papers_by_url:
                        self.papers.append(paper)
                        self.papers_by_url[url] = paper
                        paper_count += 1

            # Track file stats
            try:
                relative_path = str(file_path.relative_to(self.data_directory))
            except ValueError:
                relative_path = file_path.name
                logger.debug(
                    f"Could not determine relative path for {file_path}, using filename only"
                )

            self.stats.file_stats[relative_path] = FileStats(
                path=str(file_path),
                papers_count=paper_count,
                courses_count=course_count,
                last_modified=datetime.fromtimestamp(
                    file_path.stat().st_mtime
                ).isoformat(),
            )

            logger.debug(f"Loaded {paper_count} papers from {relative_path}")

        except orjson.JSONDecodeError as e:
            error_msg = f"Invalid JSON in {file_path.name}: {e}"
            logger.error(error_msg)
            self.stats.errors.append(error_msg)
        except Exception as e:
            error_msg = f"Error loading {file_path.name}: {e}"
            logger.error(error_msg)
            self.stats.errors.append(error_msg)

    def get_stats(self) -> Dict[str, Any]:
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
