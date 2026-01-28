"""
Library Portal API V2 - Main Application

A fresh, clean FastAPI application for serving organized question paper data.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import configuration
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config_v2 import settings

# Import routes
from .routes import papers_router, metadata_router, health_router

# Import middleware
from .middleware.auth import APIKeyMiddleware
from .middleware.security import SecurityHeadersMiddleware

# Import services
from .data_loader import DataLoader
from .services.indexing import paper_index

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
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

    loader = DataLoader(data_directory)
    paper_index.load_from_directory(loader)

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

# Add Security Headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Include routers
app.include_router(papers_router)
app.include_router(metadata_router)
app.include_router(health_router)


@app.get("/")
async def root():
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
async def api_info():
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
