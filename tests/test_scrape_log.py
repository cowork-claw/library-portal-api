"""Tests for ScrapeLog operations."""

import tempfile
from pathlib import Path

import pytest

from scraper.scrape_log import ScrapeLog


@pytest.fixture
def tmp_json_path():
    tmp_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp_path = Path(tmp_file.name)
    tmp_file.close()
    try:
        yield tmp_path
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_initialization(tmp_json_path):
    log = ScrapeLog(tmp_json_path)
    assert len(log.get_scraped_urls()) == 0
    assert not log._dirty


def test_add_url(tmp_json_path):
    log = ScrapeLog(tmp_json_path)
    url = "https://libportal.manipal.edu/RootFolder/2022/Test%20Paper.pdf"
    assert log.add_scraped_url(url) is True
    assert log.has_url(url) is True
    assert url in log.get_scraped_urls()
    assert log._dirty is True


def test_add_duplicate_url(tmp_json_path):
    log = ScrapeLog(tmp_json_path)
    url = "https://libportal.manipal.edu/RootFolder/2022/Test%20Paper.pdf"
    log.add_scraped_url(url)
    assert log.add_scraped_url(url) is False
    assert len(log.get_scraped_urls()) == 1


def test_bulk_add(tmp_json_path):
    log = ScrapeLog(tmp_json_path)
    urls = {
        "https://libportal.manipal.edu/RootFolder/2022/Paper1.pdf",
        "https://libportal.manipal.edu/RootFolder/2022/Paper2.pdf",
        "https://libportal.manipal.edu/RootFolder/2022/Paper3.pdf",
    }
    added = log.add_scraped_urls(urls)
    assert added == 3
    assert len(log.get_scraped_urls()) == 3

    # Add again with some overlap
    urls2 = {
        "https://libportal.manipal.edu/RootFolder/2022/Paper3.pdf",
        "https://libportal.manipal.edu/RootFolder/2022/Paper4.pdf",
    }
    added2 = log.add_scraped_urls(urls2)
    assert added2 == 1
    assert len(log.get_scraped_urls()) == 4


def test_persistence(tmp_json_path):
    log = ScrapeLog(tmp_json_path)
    url = "https://libportal.manipal.edu/RootFolder/2022/Persist%20Test.pdf"
    log.add_scraped_url(url)
    log.save()

    # Load in new instance
    log2 = ScrapeLog(tmp_json_path)
    assert log2.has_url(url) is True
    assert len(log2.get_scraped_urls()) == 1


def test_get_scraped_urls_is_copy(tmp_json_path):
    log = ScrapeLog(tmp_json_path)
    url = "https://libportal.manipal.edu/RootFolder/2022/Copy%20Test.pdf"
    log.add_scraped_url(url)
    urls = log.get_scraped_urls()
    urls.add("evil_url")
    assert log.has_url("evil_url") is False
