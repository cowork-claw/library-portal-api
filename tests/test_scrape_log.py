import unittest
import tempfile
import json
from pathlib import Path
from scraper.scrape_log import ScrapeLog

class TestScrapeLog(unittest.TestCase):
    def setUp(self):
        self.tmp_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmp_path = Path(self.tmp_file.name)
        self.tmp_file.close()

    def tearDown(self):
        if self.tmp_path.exists():
            self.tmp_path.unlink()

    def test_initialization(self):
        log = ScrapeLog(self.tmp_path)
        self.assertEqual(len(log.get_scraped_urls()), 0)
        self.assertFalse(log._dirty)

    def test_add_url(self):
        log = ScrapeLog(self.tmp_path)
        url = "https://example.com/1"
        self.assertTrue(log.add_scraped_url(url))
        self.assertTrue(log.has_url(url))
        self.assertIn(url, log.get_scraped_urls())
        self.assertTrue(log._dirty)

    def test_add_duplicate_url(self):
        log = ScrapeLog(self.tmp_path)
        url = "https://example.com/1"
        log.add_scraped_url(url)
        self.assertFalse(log.add_scraped_url(url))
        self.assertEqual(len(log.get_scraped_urls()), 1)

    def test_bulk_add(self):
        log = ScrapeLog(self.tmp_path)
        urls = {"url1", "url2", "url3"}
        added = log.add_scraped_urls(urls)
        self.assertEqual(added, 3)
        self.assertEqual(len(log.get_scraped_urls()), 3)

        # Add again with some overlap
        urls2 = {"url3", "url4"}
        added2 = log.add_scraped_urls(urls2)
        self.assertEqual(added2, 1)
        self.assertEqual(len(log.get_scraped_urls()), 4)

    def test_persistence(self):
        log = ScrapeLog(self.tmp_path)
        url = "https://example.com/persist"
        log.add_scraped_url(url)
        log.save()

        # Load in new instance
        log2 = ScrapeLog(self.tmp_path)
        self.assertTrue(log2.has_url(url))
        self.assertEqual(len(log2.get_scraped_urls()), 1)

    def test_get_scraped_urls_is_copy(self):
        log = ScrapeLog(self.tmp_path)
        url = "url1"
        log.add_scraped_url(url)
        urls = log.get_scraped_urls()
        urls.add("evil_url")
        self.assertFalse(log.has_url("evil_url"))

if __name__ == "__main__":
    unittest.main()
