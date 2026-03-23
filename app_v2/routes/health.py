"""
Health Routes for Library Portal API V2

Comprehensive health check endpoints for monitoring system status.
"""

import json
from datetime import datetime

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from config.config_v2 import settings

from ..models import (
    ComponentHealth,
    DataHealthResponse,
    HealthResponse,
    ScraperHealthResponse,
)
from ..services.indexing import paper_index

router = APIRouter(prefix="/health", tags=["Health"])

# Track application start time
APP_START_TIME = datetime.now()


@router.get("", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint.

    Returns overall system health status with component breakdown.
    """
    uptime = (datetime.now() - APP_START_TIME).total_seconds()

    # Check data component
    data_healthy = paper_index.total_papers > 0
    data_status = ComponentHealth(
        status="healthy" if data_healthy else "unhealthy",
        message=(
            f"Loaded {paper_index.total_papers} papers"
            if data_healthy
            else "No papers loaded"
        ),
        details={"total": paper_index.total_papers, "files": paper_index.files_loaded},
    )

    # Check scraper log
    scraper_status = await run_in_threadpool(_check_scraper_health)

    # Check staging
    staging_status = await run_in_threadpool(_check_staging_health)

    # Overall status
    overall = "healthy"
    if not data_healthy:
        overall = "unhealthy"
    elif scraper_status.status != "healthy":
        overall = "degraded"

    return HealthResponse(
        status=overall,
        timestamp=datetime.now().isoformat(),
        version=settings.APP_VERSION,
        uptime_seconds=round(uptime, 2),
        components={
            "data": data_status,
            "scraper": scraper_status,
            "staging": staging_status,
        },
    )


@router.get("/data", response_model=DataHealthResponse)
async def data_health():
    """
    Detailed data health check.

    Returns comprehensive information about loaded papers and data integrity.
    """
    loader_stats = paper_index.loader.get_stats() if paper_index.loader else {}

    return DataHealthResponse(
        status="healthy" if paper_index.total_papers > 0 else "unhealthy",
        total_papers=paper_index.total_papers,
        unique_urls=loader_stats.get("unique_urls", 0),
        files_loaded=paper_index.files_loaded,
        courses_count=len(paper_index.unique_course_codes),
        last_loaded=loader_stats.get("last_loaded"),
        errors=loader_stats.get("errors", []),
        papers_by_year=paper_index.count_by_year,
        papers_by_program=paper_index.count_by_program,
    )


@router.get("/scraper", response_model=ScraperHealthResponse)
async def scraper_health():
    """
    Scraper health check.

    Returns scraper run history and configuration.
    """
    log_data = await run_in_threadpool(_load_scrape_log)

    runs = log_data.get("runs", [])
    last_run = runs[-1] if runs else None
    stats = log_data.get("stats", {})

    return ScraperHealthResponse(
        status="healthy" if log_data else "unknown",
        last_run=last_run.get("timestamp") if last_run else None,
        total_runs=len(runs),
        total_scraped=stats.get("total_scraped", 0),
        total_skipped=stats.get("total_skipped", 0),
        target_year_threshold=settings.TARGET_YEAR_THRESHOLD,
        blacklisted_years_count=len(settings.BLACKLISTED_YEARS),
    )


def _check_scraper_health() -> ComponentHealth:
    """
    Check the health of the scraper component.

    Reads the latest scraper log to determine status and last run time.

    Returns:
        ComponentHealth: Health status object for the scraper.
    """
    log_data = _load_scrape_log()

    if not log_data:
        return ComponentHealth(
            status="unknown", message="No scrape log found", details=None
        )

    runs = log_data.get("runs", [])
    if not runs:
        return ComponentHealth(
            status="healthy",
            message="Scraper configured but never run",
            details={"total_runs": 0},
        )

    last_run = runs[-1]
    return ComponentHealth(
        status="healthy",
        message=f"Last run: {last_run.get('timestamp', 'unknown')}",
        details={"total_runs": len(runs), "last_run": last_run},
    )


def _check_staging_health() -> ComponentHealth:
    """
    Check the health of the staging area.

    Verifies if there are any papers pending review in the staging file.

    Returns:
        ComponentHealth: Health status object for the staging component.
    """
    staging_file = settings.STAGING_DIRECTORY / "pending_review.json"

    if not staging_file.exists():
        return ComponentHealth(
            status="healthy", message="No pending reviews", details={"count": 0}
        )

    try:
        with open(staging_file, "r") as f:
            data = json.load(f)

        count = len(data.get("papers", []))
        return ComponentHealth(
            status="healthy",
            message=f"{count} papers pending review" if count else "No pending reviews",
            details={"count": count},
        )
    except Exception as e:
        # Use generic error message to avoid leaking internal file paths
        return ComponentHealth(
            status="degraded",
            message=f"Error reading staging file: {e.__class__.__name__}",
            details=None,
        )


def _load_scrape_log() -> dict:
    """
    Load the scraper log file safely.

    Returns:
        dict: The content of the scraper log, or an empty dict if
              the file doesn't exist or is invalid.
    """
    try:
        if settings.SCRAPE_LOG_FILE.exists():
            with open(settings.SCRAPE_LOG_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}
