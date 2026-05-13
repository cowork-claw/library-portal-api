"""Scraper paths and year-window configuration."""

from pathlib import Path
from typing import Set

# Minimum year to scrape.
TARGET_YEAR_THRESHOLD: int = 2024

# Fully processed years to skip.
BLACKLISTED_YEARS: Set[int] = set(range(2006, 2024))

# Project root directory
PROJECT_ROOT: Path = Path(__file__).parent.parent

# Organized data directory (where all JSON files are stored)
DATA_DIRECTORY: Path = PROJECT_ROOT / "data" / "classified" / "organized"

# Scrape log file (tracks what has been scraped)
SCRAPE_LOG_FILE: Path = Path(__file__).parent / "scrape_log.json"

# Staging file for papers that need manual review
STAGING_DIRECTORY: Path = PROJECT_ROOT / "staging"
STAGING_FILE: Path = STAGING_DIRECTORY / "pending_review.json"


def _should_scrape_year(year: int) -> bool:
    if year in BLACKLISTED_YEARS:
        return False
    return year >= TARGET_YEAR_THRESHOLD
