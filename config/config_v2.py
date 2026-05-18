from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Organized data directory containing all JSON files
    DATA_DIRECTORY: Path = (
        Path(__file__).parent.parent / "data" / "classified" / "organized"
    )

    # Staging directory for manual review items
    STAGING_DIRECTORY: Path = Path(__file__).parent.parent / "staging"

    # Scraper log file
    SCRAPE_LOG_FILE: Path = Path(__file__).parent.parent / "scraper" / "scrape_log.json"

    APP_TITLE: str = "Library Portal API"
    APP_DESCRIPTION: str = "API for MIT Library Question Papers"
    APP_VERSION: str = "2.0.0"

    # API Key for protected endpoints (set via environment variable)
    API_SECRET_KEY: str | None = None

    # Local development defaults; production should set explicit origins.
    CORS_ORIGINS: list[str] = [
        "http://localhost:4321",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:4321",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    TARGET_YEAR_THRESHOLD: int = 2024
    BLACKLISTED_YEARS: list[int] = list(range(2006, 2024))

    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    SENTRY_DSN: str | None = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0
    METRICS_ENABLED: bool = False

    model_config = SettingsConfigDict(
        env_prefix="LIBRARY_PORTAL_", env_file=".env", env_file_encoding="utf-8"
    )


# Convenience access
settings = Settings()
