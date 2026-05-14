import tempfile
from pathlib import Path

import pytest

from scraper.scrape_log import ScrapeLog


@pytest.fixture
def tmp_log_path():
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir) / "scrape_log.json"


def test_initialization(tmp_log_path):
    log = ScrapeLog(tmp_log_path)
    assert len(log._get_scraped_urls()) == 0


def test_add_url(tmp_log_path):
    log = ScrapeLog(tmp_log_path)
    url = "https://example.com/1"
    assert log._add_scraped_url(url)
    assert log._has_url(url)
    assert url in log._get_scraped_urls()
    log._save()
    assert ScrapeLog(tmp_log_path)._has_url(url)


def test_add_duplicate_url(tmp_log_path):
    log = ScrapeLog(tmp_log_path)
    url = "https://example.com/1"
    log._add_scraped_url(url)
    assert not log._add_scraped_url(url)
    assert len(log._get_scraped_urls()) == 1


def test_persistence(tmp_log_path):
    log = ScrapeLog(tmp_log_path)
    url = "https://example.com/persist"
    log._add_scraped_url(url)
    log._save()

    # Load in new instance
    log2 = ScrapeLog(tmp_log_path)
    assert log2._has_url(url)
    assert len(log2._get_scraped_urls()) == 1


def test_get_scraped_urls_is_copy(tmp_log_path):
    log = ScrapeLog(tmp_log_path)
    url = "url1"
    log._add_scraped_url(url)
    urls = log._get_scraped_urls()
    urls.add("evil_url")
    assert not log._has_url("evil_url")
