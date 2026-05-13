import re

# Import V2 configuration
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urljoin

import scrapy
from scrapy import FormRequest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scrape_log import ScrapeLog, load_existing_urls_from_organized_data
from scraper_config import (
    BLACKLISTED_YEARS,
    DATA_DIRECTORY,
    SCRAPE_LOG_FILE,
    TARGET_YEAR_THRESHOLD,
)
from scraper_config import (
    should_scrape_year as config_should_scrape_year,
)

PROGRAM_NAMES = (
    "B.Tech",
    "M.Tech",
    "B.Sc",
    "M.Sc",
    "MBA",
    "MCA",
    "B.Com",
    "M.Com",
    "BBA",
    "BCA",
)


class QuestionPapersEnhancedSpider(scrapy.Spider):
    name = "question_papers_enhanced"
    allowed_domains = ["libportal.manipal.edu"]
    start_urls = ["https://libportal.manipal.edu/MIT/Question%20Paper.aspx"]

    # Custom settings for this spider
    custom_settings = {
        "DOWNLOAD_DELAY": 1,
        "CONCURRENT_REQUESTS": 4,
        "COOKIES_ENABLED": True,
        "DUPEFILTER_CLASS": "scrapy.dupefilters.BaseDupeFilter",  # Disable duplicate filtering
    }

    # Skip patterns
    SKIP_PATTERNS = [
        "Source Publication List",
        "Policy, Rules & Regulations",
        "MAHE Plagiarism report",
        "Faculty / Staff",
        "Students",
        "Agreement",
        "Open Access",
    ]

    # V2: Only scrape from threshold year onwards
    # Years 2006-2023 are blacklisted (already organized)
    TARGET_YEAR_THRESHOLD = TARGET_YEAR_THRESHOLD

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.navigation_stack = []
        self.pdf_count = 0
        self.folder_count = 0
        self.new_pdf_count = 0
        self.skipped_pdf_count = 0

        # Load existing data and create seen URLs set
        self.seen_urls = set()
        self.seen_folders = set()  # Track visited folders to prevent loops
        self.is_incremental = False
        self.current_year = datetime.now().year
        self.load_existing_data()

    def load_existing_data(self):
        """Load existing URLs from organized data folder and scrape log."""
        # V2: Load from organized data folder
        self.seen_urls = load_existing_urls_from_organized_data(DATA_DIRECTORY)

        # Also load from scrape log (URLs we've seen but may not be categorized yet)
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

    def should_scrape_year(self, year):
        """V2: Use config-based year filtering."""
        try:
            year_int = int(year)
        except (ValueError, TypeError):
            return False

        # V2: Use centralized config logic
        # This checks: not in BLACKLISTED_YEARS and >= TARGET_YEAR_THRESHOLD
        return config_should_scrape_year(year_int)

    def parse(self, response):
        """Parse any page and handle navigation."""
        current_path = self.get_current_path(response)
        depth = response.meta.get("depth", 0)

        self.logger.info(f"Parsing page - Path: {current_path}, Depth: {depth}")

        items = self.extract_items(response)
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
            if item.get("is_folder") and not self.should_skip(item["name"])
        ]
        return pdfs, folders

    def _iter_new_pdf_items(self, pdfs, response):
        """Yield unseen PDF items and update scrape counters."""
        for pdf in pdfs:
            pdf_item = self.create_pdf_item(pdf, response)
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
            if not self.should_scrape_year(folder_name):
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

        form_data = self.extract_form_data(response)
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

    def extract_form_data(self, response):
        """Extract all form data needed for ASP.NET postback."""
        form_data = {}

        # Extract all hidden fields
        for field in response.css('input[type="hidden"]'):
            name = field.css("::attr(name)").get()
            value = field.css("::attr(value)").get("")
            if name:
                form_data[name] = value

        # Add any additional form fields that might be needed
        for field in response.css('input[type="text"], input[type="submit"], select'):
            name = field.css("::attr(name)").get()
            value = field.css("::attr(value)").get("")
            if name and name not in form_data:
                form_data[name] = value

        return form_data

    def extract_items(self, response):
        """Extract all items from the current page."""
        items = []

        # Look for the specific file table
        table = response.css('table[id*="gvFiles"]').get()

        if not table:
            self.logger.debug("No file table found with gvFiles ID")
            return items

        # Parse the table
        table_selector = response.css('table[id*="gvFiles"]')
        rows = table_selector.css("tr")[1:]  # Skip header row

        self.logger.debug(f"Found table with {len(rows)} rows")

        for row in rows:
            item = self.extract_item_from_row(row, response)
            if item and item.get("name"):
                items.append(item)

        return items

    def extract_item_from_row(self, row, response):
        """Extract item data from a table row."""
        cells = row.css("td")
        if len(cells) < 2:
            return None

        first_cell = cells[0]
        link_elem = first_cell.css("a")
        if not link_elem.get():
            return None

        name = self._extract_link_name(first_cell, link_elem)
        if not name or name in ["..", "."]:
            return None

        href = link_elem.css("::attr(href)").get("")
        link_id = link_elem.css("::attr(id)").get("")
        item_type = cells[1].css("::text").get("").strip()
        size = cells[3].css("::text").get("").strip() if len(cells) > 3 else ""
        is_folder, is_pdf, event_target, event_argument, pdf_url = self._classify_item(
            name, item_type, href, link_id, response
        )

        return {
            "name": name,
            "type": item_type,
            "size": size,
            "is_folder": is_folder,
            "is_pdf": is_pdf,
            "href": href,
            "event_target": event_target,
            "event_argument": event_argument,
            "pdf_url": pdf_url,
        }

    def _extract_link_name(self, first_cell, link_elem):
        """Extract display text from the table-row link."""
        full_text = "".join(first_cell.css("a ::text").getall()).strip()
        if full_text:
            return full_text

        link_html = link_elem.get()
        text_match = re.search(r"</?\w+[^>]*>\s*([^<]+)", link_html or "")
        return text_match.group(1).strip() if text_match else ""

    def _postback_target(self, href, link_id):
        """Extract ASP.NET postback navigation target from a link."""
        if "__doPostBack" not in href:
            return False, None, None

        postback_match = re.search(r"__doPostBack\('([^']+)','([^']*)'\)", href)
        if postback_match:
            return True, postback_match.group(1), postback_match.group(2)
        if link_id:
            return True, link_id, ""
        return False, None, None

    def _pdf_url(self, name_lower, item_type_lower, href, response):
        """Return a direct PDF URL when the row points at a PDF."""
        if ".pdf" not in name_lower and "pdf" not in item_type_lower:
            return False, None
        if not href or href.startswith("javascript:"):
            return True, None
        if href.startswith("http"):
            return True, href
        return True, urljoin(response.url, href)

    def _classify_item(self, name, item_type, href, link_id, response):
        """Classify a row as folder/PDF and extract navigation metadata."""
        name_lower = name.lower()
        item_type_lower = item_type.lower()
        is_folder, event_target, event_argument = self._postback_target(href, link_id)
        is_pdf, pdf_url = self._pdf_url(name_lower, item_type_lower, href, response)

        if not is_folder and not is_pdf:
            if "folder" in item_type_lower:
                is_folder = True
            elif "pdf" in item_type_lower:
                is_pdf = True

        return is_folder, is_pdf, event_target, event_argument, pdf_url

    def should_skip(self, name):
        """Check if a folder should be skipped."""
        for pattern in self.SKIP_PATTERNS:
            if pattern.lower() in name.lower():
                return True
        return False

    def get_current_path(self, response):
        """Extract the current folder path."""
        # Try multiple selectors
        selectors = [
            'span[id*="lblCurrentFolder"]::text',
            'span[id*="CurrentFolder"]::text',
            "div.breadcrumb::text",
            "div.path::text",
        ]

        for selector in selectors:
            path = response.css(selector).get()
            if path:
                # Clean up the path
                path = path.replace("Viewing the folder ", "")
                path = path.replace("Current folder: ", "")
                path = re.sub(r"<[^>]+>", "", path)
                return path.strip()

        # If no path found, try to reconstruct from navigation stack
        nav_stack = response.meta.get("navigation_stack", [])
        if nav_stack:
            return " / ".join(nav_stack)

        return "Root"

    def create_pdf_item(self, item_data, response):
        """Create a PDF item from PDF data."""
        if not item_data.get("is_pdf"):
            return None

        item = {}

        # Basic fields
        item["file_name"] = item_data["name"]  # Renamed from 'title' to 'file_name'
        item["path"] = self.get_current_path(response)
        item["scraped_at"] = datetime.now().isoformat()

        # Construct the proper URL
        # The format is: https://libportal.manipal.edu/RootFolder/[full path]/[filename]
        # We need to URL encode the path components

        # Get the current path and clean it
        current_path = item["path"]

        # Build the full path
        if current_path and current_path != "Root":
            # Split path and URL encode each part
            path_parts = [part.strip() for part in current_path.split("/")]
            encoded_parts = [quote(part, safe="") for part in path_parts]
            encoded_path = "/".join(encoded_parts)

            # Encode the filename
            encoded_filename = quote(item["file_name"], safe="")

            # Construct the full URL
            item["url"] = (
                f"https://libportal.manipal.edu/RootFolder/{encoded_path}/{encoded_filename}"
            )
        else:
            # If at root, just use the filename
            encoded_filename = quote(item["file_name"], safe="")
            item["url"] = f"https://libportal.manipal.edu/RootFolder/{encoded_filename}"

        # Extract metadata from path and title
        self.extract_metadata(item)

        return item

    def extract_metadata(self, item):
        """Extract year, semester, program, and subject from item data."""
        path_parts = item["path"].split("/")
        file_name = item["file_name"]

        item["year"] = self._extract_year(path_parts, file_name)
        if not item["year"]:
            self.logger.warning(
                f"Could not extract valid year from path: {item['path']}"
            )

        program = self._extract_program(path_parts)
        if program:
            item["program"] = program

        semester = self._extract_semester(path_parts)
        if semester:
            item["semester"] = semester

        item["subject"] = self._extract_subject(file_name)

    def _extract_year(self, path_parts, file_name):
        """Extract a valid year from the first path component."""
        if not path_parts:
            return None

        potential_year = path_parts[0].strip()
        current_year = datetime.now().year
        if potential_year.isdigit() and len(potential_year) == 4:
            if self._is_valid_year(potential_year, current_year):
                return potential_year
            self.logger.warning(
                f"Year {int(potential_year)} outside valid range for paper: {file_name}"
            )
            return None

        year_match = re.search(r"\b(20\d{2})\b", potential_year)
        if year_match and self._is_valid_year(year_match.group(1), current_year):
            return year_match.group(1)
        return None

    def _is_valid_year(self, year_text, current_year):
        """Return whether a scraped year is within the accepted range."""
        year_int = int(year_text)
        return 2005 <= year_int <= current_year + 1

    def _extract_program(self, path_parts):
        """Extract the first known program component from a path."""
        for part in path_parts:
            if any(program in part for program in PROGRAM_NAMES):
                return part
        return None

    def _extract_semester(self, path_parts):
        """Extract semester text from path components."""
        for part in path_parts:
            sem_match = re.search(r"(I+|[1-9])\s*(st|nd|rd|th)?\s*[Ss]em", part)
            if sem_match:
                return sem_match.group()
        return None

    def _extract_subject(self, file_name):
        """Extract the display subject from a PDF file name."""
        subject = re.sub(r"\.pdf$", "", file_name, flags=re.IGNORECASE)
        subject_match = re.search(r"^([^(\[]+)", subject)
        return subject_match.group(1).strip() if subject_match else subject

    def closed(self, reason):
        """Called when spider closes. V2: Records run in scrape log."""
        self.logger.info(f"Spider closed: {reason}")
        self.logger.info(
            f"Scraping mode: {'INCREMENTAL (V2)' if self.is_incremental else 'INITIAL'}"
        )
        self.logger.info(f"Year threshold: {TARGET_YEAR_THRESHOLD}+")
        self.logger.info(f"Total PDFs found: {self.pdf_count}")
        self.logger.info(f"New PDFs scraped: {self.new_pdf_count}")
        self.logger.info(f"Existing PDFs skipped: {self.skipped_pdf_count}")
        self.logger.info(f"Total unique folders visited: {self.folder_count}")

        # V2: Record this run in the scrape log
        if hasattr(self, "scrape_log"):
            self.scrape_log.record_run(
                new_papers=self.new_pdf_count,
                skipped=self.skipped_pdf_count,
                errors=0,
                year_threshold=TARGET_YEAR_THRESHOLD,
                notes=f"Reason: {reason}",
            )
            self.logger.info("Run recorded in scrape log")
