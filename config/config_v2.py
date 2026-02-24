"""
Configuration for Library Portal API V2

Clean configuration using pydantic-settings for environment variable support.
"""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # ==========================================================================
    # DATA PATHS
    # ==========================================================================

    # Organized data directory containing all JSON files
    DATA_DIRECTORY: Path = (
        Path(__file__).parent.parent / "data" / "classified" / "organized"
    )

    # Staging directory for manual review items
    STAGING_DIRECTORY: Path = Path(__file__).parent.parent / "staging"

    # Scraper log file
    SCRAPE_LOG_FILE: Path = Path(__file__).parent.parent / "scraper" / "scrape_log.json"

    # ==========================================================================
    # API SETTINGS
    # ==========================================================================

    APP_TITLE: str = "Library Portal API"
    APP_DESCRIPTION: str = "API for MIT Library Question Papers"
    APP_VERSION: str = "2.0.0"

    # API Key for protected endpoints (set via environment variable)
    API_SECRET_KEY: Optional[str] = None

    # ==========================================================================
    # PAGINATION
    # ==========================================================================

    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 500

    # ==========================================================================
    # SEARCH
    # ==========================================================================

    FUZZY_SEARCH_THRESHOLD: int = 60  # Minimum fuzzy match score
    MAX_SUGGESTIONS: int = 10

    # ==========================================================================
    # CORS
    # ==========================================================================

    # Default includes common localhost ports for development
    # In production, set LIBRARY_PORTAL_CORS_ORIGINS environment variable
    # to a comma-separated list of specific allowed origins (no wildcards)
    # Note: Wildcards are incompatible with allow_credentials=True
    CORS_ORIGINS: List[str] = [
        "http://localhost:4321",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:4321",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # ==========================================================================
    # SCRAPER SETTINGS
    # ==========================================================================

    TARGET_YEAR_THRESHOLD: int = 2024
    BLACKLISTED_YEARS: List[int] = list(range(2006, 2024))

    # ==========================================================================
    # ENVIRONMENT
    # ==========================================================================

    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ==========================================================================
    # OBSERVABILITY
    # ==========================================================================
    SENTRY_DSN: Optional[str] = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0
    METRICS_ENABLED: bool = False

    model_config = SettingsConfigDict(
        env_prefix="LIBRARY_PORTAL_",
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience access
settings = get_settings()
