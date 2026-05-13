import re

import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import scrapy
from scrapy import FormRequest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scrape_log import ScrapeLog, _load_existing_urls_from_organized_data
from scraper_config import (
    BLACKLISTED_YEARS,
    DATA_DIRECTORY,
    SCRAPE_LOG_FILE,
    TARGET_YEAR_THRESHOLD,
)
from scraper_config import (
    should_scrape_year as config_should_scrape_year,
)

from .question_paper_metadata import QuestionPaperMetadataMixin
from .question_paper_row_parsing import QuestionPaperRowParsingMixin


class QuestionPapersEnhancedSpider(
    QuestionPaperRowParsingMixin, QuestionPaperMetadataMixin, scrapy.Spider
):
    name = "question_papers_enhanced"
    allowed_domains = ["libportal.manipal.edu"]
    start_urls = ["https://libportal.manipal.edu/MIT/Question%20Paper.aspx"]

    custom_settings = {
        "DOWNLOAD_DELAY": 1,
        "CONCURRENT_REQUESTS": 4,
        "COOKIES_ENABLED": True,
        "DUPEFILTER_CLASS": "scrapy.dupefilters.BaseDupeFilter",  # Disable duplicate filtering
    }

    SKIP_PATTERNS = [
        "Source Publication List",
        "Policy, Rules & Regulations",
        "MAHE Plagiarism report",
        "Faculty / Staff",
        "Students",
        "Agreement",
        "Open Access",
    ]

    TARGET_YEAR_THRESHOLD = TARGET_YEAR_THRESHOLD

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.navigation_stack = []
        self.pdf_count = 0
        self.folder_count = 0
        self.new_pdf_count = 0
        self.skipped_pdf_count = 0

        self.seen_urls = set()
        self.seen_folders = set()  # Track visited folders to prevent loops
        self.is_incremental = False
        self.current_year = datetime.now().year
        self._load_existing_data()

    def _load_existing_data(self):
        """Load existing URLs from organized data folder and scrape log."""
        self.seen_urls = _load_existing_urls_from_organized_data(DATA_DIRECTORY)

        self.scrape_log = ScrapeLog(SCRAPE_LOG_FILE)
        scrape_log_urls = self.scrape_log.get_scraped_urls()
        self.seen_urls.update(scrape_log_urls)

        if self.seen_urls:
            self.is_incremental = True
            self.logger.info(
                f"V2 MODE: Loaded {len(self.seen_urls)} existing URLs from organized data"
            )
            blacklist_min = min(BLACKLISTED_YEARS) if BLACKLISTED_YEARS else "N/A"
            blacklist_max = max(BLACKLISTED_YEARS) if BLACKLISTED_YEARS else "N/A"
            self.logger.info(
                f"Will only scrape years >= {TARGET_YEAR_THRESHOLD} (blacklisted: {blacklist_min}-{blacklist_max})"
            )
        else:
            self.logger.info("No existing data found - running initial scrape")

    def _should_scrape_year(self, year):
        """Return whether a year is within the configured scrape window."""
        try:
            year_int = int(year)
        except (ValueError, TypeError):
            return False

        return config_should_scrape_year(year_int)

    def parse(self, response):
        """Parse any page and handle navigation."""
        current_path = self._get_current_path(response)
        depth = response.meta.get("depth", 0)

        self.logger.info(f"Parsing page - Path: {current_path}, Depth: {depth}")

        items = self._extract_items(response)
        if not items:
            self.logger.warning(f"No items found at: {current_path}")
            return

        pdfs, folders = self._split_items(items)
        self.logger.info(
            f"Found {len(pdfs)} PDFs and {len(folders)} folders at: {current_path}"
        )

        yield from self._iter_new_pdf_items(pdfs, response)

        for folder in folders:
            request = self._build_navigation_request(
                folder, response, current_path, depth
            )
            if request:
                yield request

    def _split_items(self, items):
        """Split extracted table items into PDFs and navigable folders."""
        pdfs = [item for item in items if item.get("is_pdf")]
        folders = [
            item
            for item in items
            if item.get("is_folder") and not self._should_skip(item["name"])
        ]
        return pdfs, folders

    def _iter_new_pdf_items(self, pdfs, response):
        """Yield unseen PDF items and update scrape counters."""
        for pdf in pdfs:
            pdf_item = self._create_pdf_item(pdf, response)
            if not pdf_item:
                continue

            self.pdf_count += 1
            if pdf_item["url"] in self.seen_urls:
                self.skipped_pdf_count += 1
                self.logger.debug(
                    f"Skipping already scraped PDF: {pdf_item['file_name']}"
                )
                continue

            self.new_pdf_count += 1
            self.logger.info(f"Found NEW PDF: {pdf_item['file_name']}")
            yield pdf_item

    def _should_visit_folder(self, folder_name, current_path):
        """Return whether a folder is inside the configured scrape window."""
        if folder_name.isdigit():
            if not self._should_scrape_year(folder_name):
                self.logger.info(
                    f"Skipping year folder '{folder_name}' based on scraping mode"
                )
                return False
            self.logger.info(f"Will scrape year folder '{folder_name}'")
            return True

        return self._path_contains_target_year(current_path)

    def _path_contains_target_year(self, current_path):
        """Check whether the current folder path is within a target year."""
        for year in range(self.current_year, self.current_year + 5):
            if str(year) in current_path:
                return True

        if self.is_incremental:
            return False

        for year in range(TARGET_YEAR_THRESHOLD, self.current_year + 5):
            if str(year) in current_path:
                return True

        return False

    def _build_navigation_request(self, folder, response, current_path, depth):
        """Create a postback request for a folder, or None if it should not be visited."""
        folder_name = folder["name"]
        if not self._should_visit_folder(folder_name, current_path):
            return None

        if "event_target" not in folder or "event_argument" not in folder:
            return None

        event_target = folder["event_target"]
        event_argument = folder["event_argument"]
        folder_signature = (event_target, event_argument)
        if folder_signature in self.seen_folders:
            self.logger.debug(f"Skipping already visited folder: {folder_name}")
            return None

        self.seen_folders.add(folder_signature)
        self.folder_count += 1

        form_data = self._extract_form_data(response)
        form_data["__EVENTTARGET"] = event_target
        form_data["__EVENTARGUMENT"] = event_argument

        self.logger.info(f"Navigating to folder: {folder_name} (depth: {depth + 1})")
        return FormRequest(
            url=response.url,
            formdata=form_data,
            callback=self.parse,
            meta={
                "folder_name": folder_name,
                "parent_path": current_path,
                "depth": depth + 1,
                "navigation_stack": response.meta.get("navigation_stack", [])
                + [folder_name],
            },
            dont_filter=True,
            priority=10 - depth,
        )

    def _should_skip(self, name):
        """Check if a folder should be skipped."""
        for pattern in self.SKIP_PATTERNS:
            if pattern.lower() in name.lower():
                return True
        return False

    def _get_current_path(self, response):
        """Extract the current folder path."""
        selectors = [
            'span[id*="lblCurrentFolder"]::text',
            'span[id*="CurrentFolder"]::text',
            "div.breadcrumb::text",
            "div.path::text",
        ]

        for selector in selectors:
            path = response.css(selector).get()
            if path:
                path = path.replace("Viewing the folder ", "")
                path = path.replace("Current folder: ", "")
                path = re.sub(r"<[^>]+>", "", path)
                return path.strip()

        # If no path found, try to reconstruct from navigation stack
        nav_stack = response.meta.get("navigation_stack", [])
        if nav_stack:
            return " / ".join(nav_stack)

        return "Root"

    def _create_pdf_item(self, item_data, response):
        """Create a PDF item from PDF data."""
        if not item_data.get("is_pdf"):
            return None

        item = {
            "file_name": item_data["name"],
            "path": self._get_current_path(response),
            "scraped_at": datetime.now().isoformat(),
        }
        current_path = item["path"]

        if current_path and current_path != "Root":
            path_parts = [part.strip() for part in current_path.split("/")]
            encoded_path = "/".join(quote(part, safe="") for part in path_parts)
            encoded_filename = quote(item["file_name"], safe="")
            item["url"] = (
                f"https://libportal.manipal.edu/RootFolder/{encoded_path}/{encoded_filename}"
            )
        else:
            encoded_filename = quote(item["file_name"], safe="")
            item["url"] = f"https://libportal.manipal.edu/RootFolder/{encoded_filename}"

        self._extract_metadata(item)
        return item

    def closed(self, reason):
        """Record scrape-log stats when Scrapy closes the spider."""
        self.logger.info(f"Spider closed: {reason}")
        self.logger.info(
            f"Scraping mode: {'INCREMENTAL (V2)' if self.is_incremental else 'INITIAL'}"
        )
        self.logger.info(f"Year threshold: {TARGET_YEAR_THRESHOLD}+")
        self.logger.info(f"Total PDFs found: {self.pdf_count}")
        self.logger.info(f"New PDFs scraped: {self.new_pdf_count}")
        self.logger.info(f"Existing PDFs skipped: {self.skipped_pdf_count}")
        self.logger.info(f"Total unique folders visited: {self.folder_count}")

        if hasattr(self, "scrape_log"):
            self.scrape_log.record_run(
                new_papers=self.new_pdf_count,
                skipped=self.skipped_pdf_count,
                errors=0,
                year_threshold=TARGET_YEAR_THRESHOLD,
                notes=f"Reason: {reason}",
            )
            self.logger.info("Run recorded in scrape log")
