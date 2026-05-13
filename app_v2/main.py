"""FastAPI application wiring for the Library Portal API."""

import logging
import os

# Import configuration
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

sys.path.insert(0, str(Path(__file__).parent.parent))
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
    setup_structured_logging,
)
from .routes import health_router, metadata_router, papers_router
from .services.indexing import paper_index

# Configure structured JSON logging (replaces basicConfig)
COMPRESSION_MINIMUM_SIZE = 1024
setup_structured_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Load paper data for the application lifespan."""
    logger.info("🚀 Starting Library Portal API V2...")

    # Load data from organized folder
    data_directory = settings.DATA_DIRECTORY
    logger.info(f"Loading data from: {data_directory}")

    try:
        loader = DataLoader(data_directory)
        paper_index.load_from_directory(loader)
    except Exception:
        logger.exception("Failed to load data — starting with empty index")
        # paper_index remains empty; API will serve zero-paper responses

    if paper_index.total_papers == 0:
        logger.warning(
            "⚠️  No papers loaded — API is running in degraded mode. "
            "Check that DATA_DIRECTORY points to valid JSON files."
        )
    else:
        logger.info(
            f"✅ Loaded {paper_index.total_papers} papers from {paper_index.files_loaded} files"
        )
        logger.info(f"   Years: {paper_index.unique_years[:5]}...")
        logger.info(f"   Courses: {len(paper_index.unique_course_codes)}")

    yield

    # Cleanup on shutdown
    logger.info("👋 Shutting down Library Portal API V2...")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_TITLE,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=_lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
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

    from fastapi import Request
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Histogram,
        generate_latest,
    )
    from starlette.middleware.base import BaseHTTPMiddleware

    REQUEST_COUNT = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "route", "status_code"],
    )
    REQUEST_LATENCY = Histogram(
        "http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "route"],
    )

    class MetricsMiddleware(BaseHTTPMiddleware):
        """Middleware to record request count and duration."""

        async def dispatch(self, request: Request, call_next: Callable) -> Response:
            if request.url.path == "/metrics":
                return await call_next(request)

            start = time.perf_counter()
            response = await call_next(request)
            duration = time.perf_counter() - start
            route = request.scope.get("route")
            route_path = getattr(route, "path", request.url.path)

            REQUEST_COUNT.labels(
                method=request.method,
                route=route_path,
                status_code=str(response.status_code),
            ).inc()
            REQUEST_LATENCY.labels(method=request.method, route=route_path).observe(
                duration
            )
            return response

    metrics_router = APIRouter(tags=["Metrics"])

    @metrics_router.get("/metrics")
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.add_middleware(MetricsMiddleware)
    app.include_router(metrics_router)

# Include routers
app.include_router(papers_router)
app.include_router(metadata_router)
app.include_router(health_router)


@app.get("/")
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "papers": {
            "total": paper_index.total_papers,
            "files": paper_index.files_loaded,
        },
        "endpoints": {
            "papers": "/api/papers",
            "metadata": "/api/metadata",
            "statistics": "/api/statistics",
            "health": "/health",
            "health_detailed": "/health/data",
        },
    }


@app.get("/api")
async def api_info() -> dict:
    """API version information."""
    return {
        "version": "2.0.0",
        "status": "healthy",
        "papers_loaded": paper_index.total_papers,
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


# For running directly with uvicorn
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app_v2.main:app", host="0.0.0.0", port=8000, reload=True)
