"""
Scraper Configuration for Library Portal V2

This file contains all configurable settings for the scraper.
Change TARGET_YEAR_THRESHOLD when transitioning to a new year (e.g., 2026 in Jan 2026).
"""

from pathlib import Path
from typing import Set

# =============================================================================
# YEAR CONFIGURATION
# =============================================================================

# Minimum year to scrape - papers from this year and above will be scraped
# Change this to 2026 in January 2026, etc.
TARGET_YEAR_THRESHOLD: int = 2024

# Years to completely skip (already scraped and organized)
# These years have been fully processed and stored in data/classified/organized/
BLACKLISTED_YEARS: Set[int] = set(range(2006, 2024))

# =============================================================================
# PATH CONFIGURATION
# =============================================================================

# Project root directory
PROJECT_ROOT: Path = Path(__file__).parent.parent

# Organized data directory (where all JSON files are stored)
DATA_DIRECTORY: Path = PROJECT_ROOT / "data" / "classified" / "organized"

# Scrape log file (tracks what has been scraped)
SCRAPE_LOG_FILE: Path = Path(__file__).parent / "scrape_log.json"

# Staging file for papers that need manual review
STAGING_DIRECTORY: Path = PROJECT_ROOT / "staging"
STAGING_FILE: Path = STAGING_DIRECTORY / "pending_review.json"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def should_scrape_year(year: int) -> bool:
    """Check if a year should be scraped based on threshold and blacklist."""
    if year in BLACKLISTED_YEARS:
        return False
    return year >= TARGET_YEAR_THRESHOLD
