import pytest
import tempfile
import json
from pathlib import Path
from scraper.scrape_log import ScrapeLog

@pytest.fixture
def tmp_log_path():
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir) / "scrape_log.json"

def test_initialization(tmp_log_path):
    log = ScrapeLog(tmp_log_path)
    assert len(log.get_scraped_urls()) == 0
    assert not log._dirty

def test_add_url(tmp_log_path):
    log = ScrapeLog(tmp_log_path)
    url = "https://example.com/1"
    assert log.add_scraped_url(url)
    assert log.has_url(url)
    assert url in log.get_scraped_urls()
    assert log._dirty

def test_add_duplicate_url(tmp_log_path):
    log = ScrapeLog(tmp_log_path)
    url = "https://example.com/1"
    log.add_scraped_url(url)
    assert not log.add_scraped_url(url)
    assert len(log.get_scraped_urls()) == 1

def test_bulk_add(tmp_log_path):
    log = ScrapeLog(tmp_log_path)
    urls = {"url1", "url2", "url3"}
    added = log.add_scraped_urls(urls)
    assert added == 3
    assert len(log.get_scraped_urls()) == 3

    # Add again with some overlap
    urls2 = {"url3", "url4"}
    added2 = log.add_scraped_urls(urls2)
    assert added2 == 1
    assert len(log.get_scraped_urls()) == 4

def test_persistence(tmp_log_path):
    log = ScrapeLog(tmp_log_path)
    url = "https://example.com/persist"
    log.add_scraped_url(url)
    log.save()

    # Load in new instance
    log2 = ScrapeLog(tmp_log_path)
    assert log2.has_url(url)
    assert len(log2.get_scraped_urls()) == 1

def test_get_scraped_urls_is_copy(tmp_log_path):
    log = ScrapeLog(tmp_log_path)
    url = "url1"
    log.add_scraped_url(url)
    urls = log.get_scraped_urls()
    urls.add("evil_url")
    assert not log.has_url("evil_url")
