import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def normalize_scrape_log_data(data: Any) -> dict[str, Any]:
    data = data if isinstance(data, dict) else {}
    data.setdefault("created_at", datetime.now().isoformat())
    data.setdefault("description", "Persistent log tracking scraped paper URLs")
    scraped_urls = data.get("scraped_urls")
    data["scraped_urls"] = (
        [url for url in scraped_urls if isinstance(url, str)]
        if isinstance(scraped_urls, list)
        else []
    )
    runs = data.get("runs")
    data["runs"] = (
        [run for run in runs if isinstance(run, dict)] if isinstance(runs, list) else []
    )
    if not isinstance(data.get("stats"), dict):
        data["stats"] = {}
    stats = data["stats"]
    for key in ("total_scraped", "total_skipped", "total_errors"):
        if not isinstance(stats.get(key), int):
            stats[key] = 0
    return data


class ScrapeLog:
    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.data = self._load()
        self._scraped_urls_set = set(self.data["scraped_urls"])
        self._dirty = False

    def _load(self) -> dict[str, Any]:
        if self.log_file.exists():
            try:
                data = json.loads(self.log_file.read_text(encoding="utf-8"))
                return normalize_scrape_log_data(data)
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Error loading scrape log, creating new: {e}")

        return normalize_scrape_log_data({})

    def _save(self) -> None:
        if not self._dirty:
            return

        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        self._dirty = False

    def _get_scraped_urls(self) -> set[str]:
        return self._scraped_urls_set.copy()

    def _record_run(
        self,
        new_papers: int,
        skipped: int,
        errors: int = 0,
        year_threshold: int = 2025,
        notes: str | None = None,
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


def _load_existing_urls_from_organized_data(data_directory: Path) -> set[str]:
    urls = set()

    if not data_directory.exists():
        logger.warning(f"Data directory not found: {data_directory}")
        return urls

    for json_file in data_directory.rglob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue

            for papers_list in data.values():
                if not isinstance(papers_list, list):
                    continue
                urls.update(
                    paper["url"]
                    for paper in papers_list
                    if isinstance(paper, dict) and paper.get("url")
                )
        except Exception as e:
            logger.error(f"Error loading {json_file}: {e}")

    logger.info(f"Loaded {len(urls)} existing URLs from organized data")
    return urls
