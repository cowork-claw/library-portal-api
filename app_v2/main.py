"""
Library Portal API V2 - Main Application

A fresh, clean FastAPI application for serving organized question paper data.
"""

import logging
import os

# Import configuration
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from .middleware.auth import OPENCLAW_BOT_API_KEY_ENV, APIKeyMiddleware
from .middleware.compression import CompressionMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .middleware.request_id import RequestIDMiddleware
from .middleware.security import SecurityHeadersMiddleware
from .middleware.structured_logging import (
    StructuredLoggingMiddleware,
    setup_structured_logging,
)
from .routes import health_router, metadata_router, papers_router
from .services.indexing import paper_index

# Configure structured JSON logging (replaces basicConfig)
setup_structured_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Loads data on startup, cleans up on shutdown.
    """
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
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add Gzip Compression middleware first so it stays innermost among the
# custom stack; auth/rate-limit errors are generated outside this layer.
app.add_middleware(CompressionMiddleware)

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
    from .middleware.metrics import MetricsMiddleware
    from .routes.metrics import router as metrics_router

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
