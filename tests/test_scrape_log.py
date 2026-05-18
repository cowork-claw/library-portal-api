import json
import tempfile
from pathlib import Path

import pytest

from scraper.scrape_log import ScrapeLog


@pytest.fixture
def tmp_log_path():
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir) / "scrape_log.json"


def _write_log(path: Path, urls: list[str]) -> None:
    path.write_text(
        json.dumps({"scraped_urls": urls, "runs": [], "stats": {}}), encoding="utf-8"
    )


def test_initialization(tmp_log_path):
    log = ScrapeLog(tmp_log_path)
    assert len(log._get_scraped_urls()) == 0


def test_loads_existing_urls(tmp_log_path):
    url = "https://example.com/1"
    _write_log(tmp_log_path, [url])

    log = ScrapeLog(tmp_log_path)

    assert url in log._get_scraped_urls()


def test_get_scraped_urls_deduplicates_loaded_data(tmp_log_path):
    url = "https://example.com/1"
    _write_log(tmp_log_path, [url, url])

    log = ScrapeLog(tmp_log_path)

    assert log._get_scraped_urls() == {url}


def test_record_run_persists_stats(tmp_log_path):
    log = ScrapeLog(tmp_log_path)

    log._record_run(new_papers=2, skipped=3, errors=1, year_threshold=2024, notes="ok")

    log2 = ScrapeLog(tmp_log_path)
    assert log2.data["runs"][-1]["notes"] == "ok"
    assert log2.data["stats"] == {
        "total_scraped": 2,
        "total_skipped": 3,
        "total_errors": 1,
    }


def test_get_scraped_urls_is_copy(tmp_log_path):
    url = "url1"
    _write_log(tmp_log_path, [url])
    log = ScrapeLog(tmp_log_path)

    urls = log._get_scraped_urls()
    urls.add("evil_url")

    assert log._get_scraped_urls() == {url}
