import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from time import perf_counter

from fastapi import APIRouter, BackgroundTasks, status
from fastapi.concurrency import run_in_threadpool

from config.config_v2 import settings
from scraper.scrape_log import _normalize_scrape_log_data

from ..data_loader import DataLoader
from ..models import (
    ComponentHealth,
    DataHealthResponse,
    HealthResponse,
    ReloadResponse,
    ScraperHealthResponse,
)
from ..services.indexing import paper_index

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])

# Track application start time with a monotonic clock for stable uptime.
APP_START_MONOTONIC = perf_counter()
DATA_HEALTH_OPERATION_ID = "data_health_health_data_get"
SCRAPER_HEALTH_OPERATION_ID = "scraper_health_health_scraper_get"


@router.get("", response_model=HealthResponse, operation_id="health_check_health_get")
async def _health_check() -> HealthResponse:
    """Return overall system health with component statuses."""
    # Check data component — "degraded" when no data (not "unhealthy")
    data_healthy = paper_index._paper_count > 0
    data_status = ComponentHealth(
        status="healthy" if data_healthy else "degraded",
        message=(
            f"Loaded {paper_index._paper_count} papers"
            if data_healthy
            else "No papers loaded"
        ),
        details={
            "total": paper_index._paper_count,
            "files": paper_index._loaded_file_count,
        },
    )

    # Check scraper log
    scraper_status = await run_in_threadpool(_check_scraper_health)

    # Check staging
    staging_status = await run_in_threadpool(_check_staging_health)

    overall = (
        "degraded"
        if not data_healthy or scraper_status.status != "healthy"
        else "healthy"
    )

    return HealthResponse(
        status=overall,
        timestamp=datetime.now().isoformat(),
        version=settings.APP_VERSION,
        uptime_seconds=round(perf_counter() - APP_START_MONOTONIC, 2),
        components={
            "data": data_status,
            "scraper": scraper_status,
            "staging": staging_status,
        },
    )


@router.get(
    "/data", response_model=DataHealthResponse, operation_id=DATA_HEALTH_OPERATION_ID
)
async def _data_health() -> DataHealthResponse:
    """Return loaded paper and data integrity status."""
    loader_stats = vars(paper_index.loader.stats) if paper_index.loader else {}

    return DataHealthResponse(
        status="healthy" if paper_index._paper_count > 0 else "degraded",
        total_papers=paper_index._paper_count,
        unique_urls=loader_stats.get("unique_urls", 0),
        files_loaded=paper_index._loaded_file_count,
        courses_count=len(paper_index._unique_course_code_values),
        last_loaded=loader_stats.get("last_loaded"),
        errors=loader_stats.get("errors", []),
        papers_by_year=dict(paper_index._count_by_year_values),
        papers_by_program=dict(paper_index._count_by_program_values),
    )


@router.get(
    "/scraper",
    response_model=ScraperHealthResponse,
    operation_id=SCRAPER_HEALTH_OPERATION_ID,
)
async def _scraper_health() -> ScraperHealthResponse:
    """Return scraper run history and configuration status."""
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


@router.post(
    "/data/reload",
    response_model=ReloadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="reload_data_health_data_reload_post",
)
async def _reload_data(background_tasks: BackgroundTasks) -> ReloadResponse:
    """Schedule a background JSON data reload."""
    reload_id = str(uuid.uuid4())
    # Read DATA_DIRECTORY directly from env so reload always uses the current
    # value, even if the module-level ``settings`` is stale after tests reload
    # config.  This mirrors how ``Settings`` itself resolves the value.
    data_directory = Path(
        os.environ.get("LIBRARY_PORTAL_DATA_DIRECTORY", str(settings.DATA_DIRECTORY))
    )

    background_tasks.add_task(_do_reload, reload_id, data_directory)

    return ReloadResponse(reload_id=reload_id, message="Reload started")


def _do_reload(reload_id: str, data_directory) -> None:
    try:
        paper_index._reload_from_directory(DataLoader(data_directory))
        logger.info(
            "Reload %s complete: %d papers loaded", reload_id, paper_index._paper_count
        )
    except Exception:
        logger.exception("Reload %s failed", reload_id)


def _check_scraper_health() -> ComponentHealth:
    log_data = _load_scrape_log()

    if not log_data:
        return ComponentHealth(status="unknown", message="No scrape log found")

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
    staging_file = settings.STAGING_DIRECTORY / "pending_review.json"

    if not staging_file.exists():
        return ComponentHealth(
            status="healthy", message="No pending reviews", details={"count": 0}
        )

    try:
        data = json.loads(staging_file.read_text(encoding="utf-8"))
        papers = data.get("papers", []) if isinstance(data, dict) else None
        if not isinstance(papers, list) or any(
            not isinstance(paper, dict) or not isinstance(paper.get("paper", {}), dict)
            for paper in papers
        ):
            raise ValueError("Invalid staging file shape")
        count = len(papers)
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
        )


def _load_scrape_log() -> dict:
    try:
        return _normalize_scrape_log_data(
            json.loads(settings.SCRAPE_LOG_FILE.read_text(encoding="utf-8"))
        )
    except Exception:
        return {}
