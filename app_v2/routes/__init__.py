"""Routes package for Library Portal API V2."""

from .papers import router as papers_router
from .metadata import router as metadata_router
from .health import router as health_router

__all__ = ["papers_router", "metadata_router", "health_router"]
