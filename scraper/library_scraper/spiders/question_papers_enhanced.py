import scrapy
from scrapy import FormRequest, Request
import re
from datetime import datetime
from urllib.parse import urljoin, quote
import json
import os
from pathlib import Path

# Import V2 configuration
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scraper_config import (
    TARGET_YEAR_THRESHOLD,
    BLACKLISTED_YEARS,
    DATA_DIRECTORY,
    SCRAPE_LOG_FILE,
    should_scrape_year as config_should_scrape_year
)
from scrape_log import ScrapeLog, load_existing_urls_from_organized_data


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
    # Years 2006-2024 are blacklisted (already organized)
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
            self.logger.info(
                f"Will only scrape years >= {TARGET_YEAR_THRESHOLD} (blacklisted: 2006-2024)"
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

        # Extract all items on current page
        items = self.extract_items(response)

        if not items:
            self.logger.warning(f"No items found at: {current_path}")
            return

        # Log what we found
        pdfs = [item for item in items if item.get("is_pdf")]
        folders = [
            item
            for item in items
            if item.get("is_folder") and not self.should_skip(item["name"])
        ]

        self.logger.info(
            f"Found {len(pdfs)} PDFs and {len(folders)} folders at: {current_path}"
        )

        # Process PDFs
        for pdf in pdfs:
            pdf_item = self.create_pdf_item(pdf, response)
            if pdf_item:
                self.pdf_count += 1

                # Check if URL has been seen before
                if pdf_item["url"] in self.seen_urls:
                    self.skipped_pdf_count += 1
                    self.logger.debug(
                        f"Skipping already scraped PDF: {pdf_item['file_name']}"
                    )
                    continue

                # This is a new PDF
                self.new_pdf_count += 1
                self.logger.info(f"Found NEW PDF: {pdf_item['title']}")
                yield pdf_item

        # Process folders
        for folder in folders:
            folder_name = folder["name"]

            # Check if it's a year folder
            is_year_folder = folder_name.isdigit()

            if is_year_folder:
                # Decide whether to scrape this year
                if not self.should_scrape_year(folder_name):
                    self.logger.info(
                        f"Skipping year folder '{folder_name}' based on scraping mode"
                    )
                    continue
                else:
                    self.logger.info(f"Will scrape year folder '{folder_name}'")

            # For non-year folders, check if we're inside a target year
            is_in_target_year = False
            if not is_year_folder:
                # Check if current path contains a year we should scrape
                for year in range(
                    self.current_year, self.current_year + 5
                ):  # Check current and next 4 years
                    if str(year) in current_path:
                        is_in_target_year = True
                        break

                # Also check TARGET_YEARS if in full scrape mode
                if not self.is_incremental:
                    for year in self.TARGET_YEARS:
                        if str(year) in current_path:
                            is_in_target_year = True
                            break

            # Navigate if it's a year folder we want or we're inside a target year
            if is_year_folder or is_in_target_year:
                if "event_target" in folder and "event_argument" in folder:
                    # Create unique folder signature
                    event_target = folder["event_target"]
                    event_argument = folder["event_argument"]
                    folder_signature = (event_target, event_argument)

                    # Check if we've already visited this folder
                    if folder_signature in self.seen_folders:
                        self.logger.debug(
                            f"Skipping already visited folder: {folder['name']}"
                        )
                        continue

                    # Mark this folder as seen
                    self.seen_folders.add(folder_signature)
                    self.folder_count += 1

                    # Prepare form data for navigation
                    form_data = self.extract_form_data(response)
                    form_data["__EVENTTARGET"] = event_target
                    form_data["__EVENTARGUMENT"] = event_argument

                    # Log navigation attempt
                    self.logger.info(
                        f"Navigating to folder: {folder['name']} (depth: {depth + 1})"
                    )

                    yield FormRequest(
                        url=response.url,
                        formdata=form_data,
                        callback=self.parse,
                        meta={
                            "folder_name": folder["name"],
                            "parent_path": current_path,
                            "depth": depth + 1,
                            "navigation_stack": response.meta.get(
                                "navigation_stack", []
                            )
                            + [folder["name"]],
                        },
                        dont_filter=True,
                        priority=10 - depth,  # Higher priority for shallower folders
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

        # First cell contains the link
        first_cell = cells[0]
        link = first_cell.css("a").get()

        if not link:
            return None

        # Extract the link element for detailed parsing
        link_elem = first_cell.css("a")

        # Extract name - it's after the image tag
        # The structure is: <img src="../Images/folder.png" alt="" />&nbsp;2023
        full_text = "".join(first_cell.css("a ::text").getall()).strip()

        # If no text found, try extracting from the full HTML
        if not full_text:
            link_html = link_elem.get()
            # Look for text after the image tag
            text_match = re.search(r"</?\w+[^>]*>\s*([^<]+)", link_html)
            if text_match:
                full_text = text_match.group(1).strip()

        name = full_text
        if not name or name in ["..", "."]:
            return None

        # Extract href and ID
        href = link_elem.css("::attr(href)").get("")
        link_id = link_elem.css("::attr(id)").get("")

        # Extract type and size from other cells
        item_type = cells[1].css("::text").get("").strip() if len(cells) > 1 else ""
        size = cells[3].css("::text").get("").strip() if len(cells) > 3 else ""

        # Determine if it's a folder or PDF
        is_folder = False
        is_pdf = False
        event_target = None
        event_argument = None
        pdf_url = None

        # Check for postback (folder navigation)
        if "__doPostBack" in href:
            postback_match = re.search(r"__doPostBack\('([^']+)','([^']*)'\)", href)
            if postback_match:
                is_folder = True
                event_target = postback_match.group(1)
                event_argument = postback_match.group(2)
            elif link_id:
                # Use the link ID as event target
                is_folder = True
                event_target = link_id
                event_argument = ""

        # Check for PDF
        if ".pdf" in name.lower() or "pdf" in item_type.lower():
            is_pdf = True

            # For PDFs, the href might be a direct link
            if href and not href.startswith("javascript:"):
                pdf_url = href
                if not pdf_url.startswith("http"):
                    pdf_url = urljoin(response.url, pdf_url)

        # Use item type as additional check
        if not is_folder and not is_pdf:
            if "folder" in item_type.lower():
                is_folder = True
            elif "pdf" in item_type.lower():
                is_pdf = True

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

        # Extract year - ONLY from the path, specifically the first element
        item["year"] = None  # Default to None

        if path_parts and len(path_parts) > 0:
            # The year should be the first element in the path
            potential_year = path_parts[0].strip()

            # Validate that it's a 4-digit number
            if potential_year.isdigit() and len(potential_year) == 4:
                year_int = int(potential_year)
                # Validate reasonable range (2005 to current year + 1)
                current_year = datetime.now().year
                if 2005 <= year_int <= current_year + 1:
                    item["year"] = potential_year
                else:
                    self.logger.warning(
                        f"Year {year_int} outside valid range for paper: {file_name}"
                    )
            else:
                # Try to extract year from first path element if it contains other text
                year_match = re.search(r"\b(20\d{2})\b", potential_year)
                if year_match:
                    year_int = int(year_match.group(1))
                    if 2005 <= year_int <= current_year + 1:
                        item["year"] = year_match.group(1)

        if not item["year"]:
            self.logger.warning(
                f"Could not extract valid year from path: {item['path']}"
            )

        # Extract program
        programs = [
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
        ]
        for part in path_parts:
            for prog in programs:
                if prog in part:
                    item["program"] = part
                    break

        # Extract semester - from path only, not title
        for part in path_parts:
            sem_match = re.search(r"(I+|[1-9])\s*(st|nd|rd|th)?\s*[Ss]em", part)
            if sem_match:
                item["semester"] = sem_match.group()
                break

        # Extract subject
        # Remove file extension
        subject = re.sub(r"\.pdf$", "", file_name, flags=re.IGNORECASE)
        # Extract text before parentheses
        subject_match = re.search(r"^([^(\[]+)", subject)
        if subject_match:
            item["subject"] = subject_match.group(1).strip()
        else:
            item["subject"] = subject

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
        if hasattr(self, 'scrape_log'):
            self.scrape_log.record_run(
                new_papers=self.new_pdf_count,
                skipped=self.skipped_pdf_count,
                errors=0,
                year_threshold=TARGET_YEAR_THRESHOLD,
                notes=f"Reason: {reason}"
            )
            self.logger.info("Run recorded in scrape log")
