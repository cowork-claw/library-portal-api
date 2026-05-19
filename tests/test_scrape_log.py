import json
import tempfile
from pathlib import Path

import pytest

from scraper.scrape_log import ScrapeLog, _load_existing_urls_from_organized_data


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


def test_record_run_normalizes_legacy_stats(tmp_log_path):
    tmp_log_path.write_text(
        json.dumps({"scraped_urls": [], "runs": [], "stats": {}}), encoding="utf-8"
    )

    log = ScrapeLog(tmp_log_path)
    log._record_run(new_papers=1, skipped=2)

    assert log.data["stats"] == {
        "total_scraped": 1,
        "total_skipped": 2,
        "total_errors": 0,
    }


def test_wrong_shaped_scrape_log_initializes_empty_log(tmp_log_path):
    tmp_log_path.write_text("[]", encoding="utf-8")

    log = ScrapeLog(tmp_log_path)

    assert log._get_scraped_urls() == set()
    assert log.data["runs"] == []


def test_health_scraper_status_tolerates_wrong_shaped_log(tmp_log_path, monkeypatch):
    from app_v2.routes import health

    tmp_log_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(health.settings, "SCRAPE_LOG_FILE", tmp_log_path)

    status = health._check_scraper_health()

    assert status.status == "healthy"
    assert status.details == {"total_runs": 0}


def test_existing_url_loader_skips_malformed_paper_items(tmp_path):
    data_file = tmp_path / "organized.json"
    data_file.write_text(
        json.dumps(
            {
                "BAD101": ["bad item", {"url": "https://example.com/good.pdf"}],
                "BAD102": "not a list",
            }
        ),
        encoding="utf-8",
    )

    assert _load_existing_urls_from_organized_data(tmp_path) == {
        "https://example.com/good.pdf"
    }


def test_existing_url_loader_skips_wrong_shaped_json_files(tmp_path):
    (tmp_path / "bad.json").write_text("[]", encoding="utf-8")
    (tmp_path / "good.json").write_text(
        json.dumps({"GOOD101": [{"url": "https://example.com/good.pdf"}]}),
        encoding="utf-8",
    )

    assert _load_existing_urls_from_organized_data(tmp_path) == {
        "https://example.com/good.pdf"
    }
