import logging
import os

# Import configuration
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from config.config_v2 import settings

# Optional error tracking (enabled only when SENTRY_DSN is set)
if settings.SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[FastApiIntegration()],
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
    )

# Import routes
# Import services
from .data_loader import DataLoader

# Import middleware
from .middleware.auth import (
    OPENCLAW_BOT_API_KEY_ENV,
    APIKeyMiddleware,
    SecurityHeadersMiddleware,
)
from .middleware.rate_limit import RateLimitMiddleware
from .middleware.structured_logging import (
    RequestIDMiddleware,
    StructuredLoggingMiddleware,
    _setup_structured_logging,
)
from .models import MetadataResponse, StatisticsResponse
from .routes import health_router, papers_router
from .services.indexing import paper_index

# Configure structured JSON logging (replaces basicConfig)
COMPRESSION_MINIMUM_SIZE = 1024
_setup_structured_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    logger.info("🚀 Starting Library Portal API V2...")

    # Load data from organized folder
    logger.info(f"Loading data from: {settings.DATA_DIRECTORY}")

    try:
        loader = DataLoader(settings.DATA_DIRECTORY)
        paper_index._load_from_directory(loader)
    except Exception:
        logger.exception("Failed to load data — starting with empty index")
        # paper_index remains empty; API will serve zero-paper responses

    if paper_index._paper_count == 0:
        logger.warning(
            "⚠️  No papers loaded — API is running in degraded mode. "
            "Check that DATA_DIRECTORY points to valid JSON files."
        )
    else:
        logger.info(
            f"✅ Loaded {paper_index._paper_count} papers from {paper_index._loaded_file_count} files"
        )
        logger.info(f"   Years: {paper_index._unique_year_values[:5]}...")
        logger.info(f"   Courses: {len(paper_index._unique_course_code_values)}")

    yield

    # Cleanup on shutdown
    logger.info("👋 Shutting down Library Portal API V2...")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_TITLE,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=_lifespan,
)

# Add Gzip Compression middleware first so it stays innermost among the
# custom stack; auth/rate-limit errors are generated outside this layer.
app.add_middleware(GZipMiddleware, minimum_size=COMPRESSION_MINIMUM_SIZE)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add API Key authentication middleware
# Set LIBRARY_PORTAL_API_KEY env var to enable authentication
app.add_middleware(
    APIKeyMiddleware,
    api_key=settings.API_SECRET_KEY,
    environment=settings.ENVIRONMENT,
)

# Add Rate Limiting middleware (wraps APIKey so failed auth counts toward limit)
rate_limit_valid_keys = [
    key for key in (settings.API_SECRET_KEY, os.getenv(OPENCLAW_BOT_API_KEY_ENV)) if key
]
app.add_middleware(RateLimitMiddleware, valid_api_keys=rate_limit_valid_keys)

# Add Security Headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add Structured Logging middleware
# (inside RequestID so it can read request.state.request_id)
app.add_middleware(StructuredLoggingMiddleware)

# Add Request ID middleware (outermost — registered last so it wraps everything)
app.add_middleware(RequestIDMiddleware)

# Optional Prometheus metrics (disabled by default)
if settings.METRICS_ENABLED:
    import time
    from typing import Callable

    import prometheus_client as prom
    from fastapi import Request
    from starlette.middleware.base import BaseHTTPMiddleware

    REQUEST_COUNT = prom.Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "route", "status_code"],
    )
    REQUEST_LATENCY = prom.Histogram(
        "http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "route"],
    )

    class MetricsMiddleware(BaseHTTPMiddleware):

        async def dispatch(self, request: Request, call_next: Callable) -> Response:
            if request.url.path == "/metrics":
                return await call_next(request)

            start = time.perf_counter()
            response = await call_next(request)
            duration = time.perf_counter() - start
            route = request.scope.get("route")
            route_path = getattr(route, "path", request.url.path)

            REQUEST_COUNT.labels(
                request.method, route_path, f"{response.status_code}"
            ).inc()
            REQUEST_LATENCY.labels(request.method, route_path).observe(duration)
            return response

    metrics_router = APIRouter(tags=["Metrics"])

    @metrics_router.get("/metrics")
    def _metrics() -> Response:
        return Response(prom.generate_latest(), media_type=prom.CONTENT_TYPE_LATEST)

    app.add_middleware(MetricsMiddleware)
    app.include_router(metrics_router)

# Include routers
app.include_router(papers_router)
app.include_router(health_router)


@app.get(
    "/api/metadata",
    response_model=MetadataResponse,
    tags=["Metadata"],
    operation_id="get_metadata_api_metadata_get",
)
async def _get_metadata() -> MetadataResponse:
    """Return available filter values for clients."""
    return MetadataResponse(
        years=list(paper_index._unique_year_values),
        programs=list(paper_index._unique_program_values),
        program_abbrevs=list(paper_index._unique_program_abbrev_values),
        semesters=list(paper_index._unique_semester_values),
        paper_types=list(paper_index._unique_paper_type_values),
        degree_types=list(paper_index._unique_degree_type_values),
        course_codes=list(paper_index._unique_course_code_values[:100]),
        streams=list(paper_index._unique_stream_values),
        total_papers=paper_index._paper_count,
    )


@app.get(
    "/api/statistics",
    response_model=StatisticsResponse,
    tags=["Metadata"],
    operation_id="get_statistics_api_statistics_get",
)
async def _get_statistics() -> StatisticsResponse:
    """Return aggregate paper collection counts."""
    return StatisticsResponse(
        total_papers=paper_index._paper_count,
        papers_by_year=dict(paper_index._count_by_year_values),
        papers_by_program=dict(paper_index._count_by_program_values),
        papers_by_program_abbrev=dict(paper_index._count_by_program_abbrev_values),
        papers_by_semester=dict(paper_index._count_by_semester_values),
        courses_count=len(paper_index._unique_course_code_values),
        files_loaded=paper_index._loaded_file_count,
    )


@app.get("/", operation_id="root__get")
async def _root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "papers": {
            "total": paper_index._paper_count,
            "files": paper_index._loaded_file_count,
        },
        "endpoints": {
            "papers": "/api/papers",
            "metadata": "/api/metadata",
            "statistics": "/api/statistics",
            "health": "/health",
            "health_detailed": "/health/data",
        },
    }


@app.get("/api", operation_id="api_info_api_get")
async def _api_info() -> dict:
    """API version information."""
    return {
        "version": "2.0.0",
        "status": "healthy",
        "papers_loaded": paper_index._paper_count,
        "endpoints": [
            "GET /api/papers - List papers with filters",
            "GET /api/papers/year/{year} - Papers by year",
            "GET /api/papers/course/{code} - Papers by course",
            "GET /api/papers/semester/{sem} - Papers by semester",
            "GET /api/metadata - Available filter values",
            "GET /api/statistics - Collection statistics",
            "GET /health - System health check",
            "GET /health/data - Data health details",
            "GET /health/scraper - Scraper health",
        ],
    }
