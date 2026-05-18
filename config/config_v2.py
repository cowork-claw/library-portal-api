from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    # Organized data directory containing all JSON files
    DATA_DIRECTORY: Path = ROOT_DIR / "data" / "classified" / "organized"

    # Staging directory for manual review items
    STAGING_DIRECTORY: Path = ROOT_DIR / "staging"

    # Scraper log file
    SCRAPE_LOG_FILE: Path = ROOT_DIR / "scraper" / "scrape_log.json"

    APP_TITLE: str = "Library Portal API"
    APP_DESCRIPTION: str = "API for MIT Library Question Papers"
    APP_VERSION: str = "2.0.0"

    # API Key for protected endpoints (set via environment variable)
    API_SECRET_KEY: str | None = None

    # Local development defaults; production should set explicit origins.
    CORS_ORIGINS: list[str] = [
        f"http://{host}:{port}"
        for host in ("localhost", "127.0.0.1")
        for port in (4321, 3000, 5173)
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
