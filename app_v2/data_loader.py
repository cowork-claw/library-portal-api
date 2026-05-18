import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import orjson

logger = logging.getLogger(__name__)


@dataclass
class LoaderStats:

    total_papers: int = 0
    unique_urls: int = 0
    files_loaded: int = 0
    last_loaded: str | None = None
    file_stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class DataLoader:

    def __init__(self, data_directory: Path):
        self.data_directory = data_directory
        self.papers: list[dict[str, Any]] = []
        self.seen_urls: set[str] = set()
        self.stats = LoaderStats()

    def _load_all(self) -> list[dict[str, Any]]:
        self.papers = []
        self.seen_urls = set()
        self.stats = LoaderStats()

        if not self.data_directory.exists():
            logger.warning("Data directory not found: %s", self.data_directory.name)
            self.stats.errors.append("Data directory not found")
            return []

        for json_file in self.data_directory.rglob("*.json"):
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

    def _add_unique_papers_from_file(
        self, file_path: Path, data: dict[str, Any]
    ) -> tuple[int, int]:
        paper_count = course_count = 0
        for course_code, papers_list in data.items():
            if not isinstance(papers_list, list):
                logger.warning(
                    f"Invalid format in {file_path.name}: {course_code} is not a list"
                )
                continue

            course_count += 1
            for paper in papers_list:
                if (url := paper.get("url")) and url not in self.seen_urls:
                    self.papers.append(paper)
                    self.seen_urls.add(url)
                    paper_count += 1

        return paper_count, course_count

    def _load_file(self, file_path: Path) -> None:
        try:
            data = orjson.loads(file_path.read_bytes())
            paper_count, course_count = self._add_unique_papers_from_file(
                file_path, data
            )
            relative_path = str(file_path.relative_to(self.data_directory))
            self.stats.file_stats[relative_path] = {
                "papers": paper_count,
                "courses": course_count,
                "modified": datetime.fromtimestamp(
                    file_path.stat().st_mtime
                ).isoformat(),
            }
        except orjson.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {file_path.name}: {e}")
            self.stats.errors.append(
                f"Invalid JSON in {file_path.name}: {e.__class__.__name__}"
            )
        except Exception as e:
            logger.error(f"Error loading {file_path.name}: {e}")
            self.stats.errors.append(
                f"Error loading {file_path.name}: {e.__class__.__name__}"
            )
