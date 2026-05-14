import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)


class ScrapeLog:
    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.data = self._load()
        self._scraped_urls_set = set(self.data.setdefault("scraped_urls", []))
        self._dirty = False

    def _load(self) -> Dict[str, Any]:
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

    def _save(self) -> None:
        if not self._dirty:
            return

        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
        self._dirty = False
        logger.debug(f"Saved scrape log to {self.log_file}")

    def _get_scraped_urls(self) -> Set[str]:
        return self._scraped_urls_set.copy()

    def _has_url(self, url: str) -> bool:
        return url in self._scraped_urls_set

    def _add_scraped_url(self, url: str) -> bool:
        if url not in self._scraped_urls_set:
            self._scraped_urls_set.add(url)
            self.data["scraped_urls"].append(url)
            self._dirty = True
            return True
        return False

    def _record_run(
        self,
        new_papers: int,
        skipped: int,
        errors: int = 0,
        year_threshold: int = 2025,
        notes: Optional[str] = None,
    ) -> None:
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
        self._save()

        logger.info(
            f"Recorded run: {new_papers} new, {skipped} skipped, {errors} errors"
        )


def _load_existing_urls_from_organized_data(data_directory: Path) -> Set[str]:
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
