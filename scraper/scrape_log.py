"""
Scrape Log Manager for Library Portal V2

Persistent log tracking scraped paper URLs to avoid re-scraping.
Acts as "memory" for the scraper across runs.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Set, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ScrapeLog:
    """
    Persistent scrape log manager.

    Tracks:
    - All scraped URLs (for deduplication)
    - Run history with timestamps and counts
    - Error counts and messages
    """

    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.data = self._load()
        self._dirty = False

    def _load(self) -> Dict[str, Any]:
        """Load existing log or create new."""
        if self.log_file.exists():
            try:
                with open(self.log_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(
                    f"Loaded scrape log with {len(data.get('scraped_urls', []))} URLs"
                )
                return data
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Error loading scrape log, creating new: {e}")

        return {
            "created_at": datetime.now().isoformat(),
            "description": "Persistent log tracking scraped paper URLs",
            "scraped_urls": [],
            "runs": [],
            "stats": {"total_scraped": 0, "total_skipped": 0, "total_errors": 0},
        }

    def save(self) -> None:
        """Save log to file."""
        if not self._dirty:
            return

        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
        self._dirty = False
        logger.debug(f"Saved scrape log to {self.log_file}")

    def get_scraped_urls(self) -> Set[str]:
        """Get all previously scraped URLs."""
        return set(self.data.get("scraped_urls", []))

    def has_url(self, url: str) -> bool:
        """Check if URL has already been scraped."""
        return url in self.get_scraped_urls()

    def add_scraped_url(self, url: str) -> bool:
        """
        Add URL to scraped list.

        Returns:
            True if URL was new, False if already existed
        """
        if url not in self.data["scraped_urls"]:
            self.data["scraped_urls"].append(url)
            self._dirty = True
            return True
        return False

    def add_scraped_urls(self, urls: Set[str]) -> int:
        """
        Bulk add URLs to scraped list.

        Returns:
            Number of new URLs added
        """
        existing = set(self.data["scraped_urls"])
        new_urls = urls - existing
        if new_urls:
            self.data["scraped_urls"].extend(new_urls)
            self._dirty = True
        return len(new_urls)

    def record_run(
        self,
        new_papers: int,
        skipped: int,
        errors: int = 0,
        year_threshold: int = 2025,
        notes: Optional[str] = None,
    ) -> None:
        """Record a scraper run with statistics."""
        run_record = {
            "timestamp": datetime.now().isoformat(),
            "new_papers": new_papers,
            "skipped": skipped,
            "errors": errors,
            "year_threshold": year_threshold,
        }
        if notes:
            run_record["notes"] = notes

        self.data["runs"].append(run_record)
        self.data["stats"]["total_scraped"] += new_papers
        self.data["stats"]["total_skipped"] += skipped
        self.data["stats"]["total_errors"] += errors
        self._dirty = True
        self.save()

        logger.info(
            f"Recorded run: {new_papers} new, {skipped} skipped, {errors} errors"
        )

    def get_last_run(self) -> Optional[Dict[str, Any]]:
        """Get the most recent run record."""
        runs = self.data.get("runs", [])
        return runs[-1] if runs else None

    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics."""
        return {
            "total_urls": len(self.data.get("scraped_urls", [])),
            "total_runs": len(self.data.get("runs", [])),
            **self.data.get("stats", {}),
        }


def load_existing_urls_from_organized_data(data_directory: Path) -> Set[str]:
    """
    Load all existing paper URLs from organized JSON files.

    This is used to initialize the scraper's "seen" set from existing data.
    """
    urls = set()

    if not data_directory.exists():
        logger.warning(f"Data directory not found: {data_directory}")
        return urls

    json_files = list(data_directory.rglob("*.json"))
    logger.info(f"Loading existing URLs from {len(json_files)} JSON files")

    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for course_code, papers_list in data.items():
                if isinstance(papers_list, list):
                    for paper in papers_list:
                        url = paper.get("url")
                        if url:
                            urls.add(url)
        except Exception as e:
            logger.error(f"Error loading {json_file}: {e}")

    logger.info(f"Loaded {len(urls)} existing URLs from organized data")
    return urls
