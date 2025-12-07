"""
API Authentication Middleware for Library Portal V2

Protects API endpoints with API key authentication.
Public endpoints (health, docs) are accessible without authentication.
"""

import os
from typing import Optional, Callable
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)

# Environment variable for API key
API_KEY_ENV = "LIBRARY_PORTAL_API_KEY"

# Public paths that don't require authentication
PUBLIC_PATHS = {
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
    "/health/",
    "/health/data",
    "/health/scraper",
    "/api",
}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware for API key authentication.

    API key can be provided via:
    1. Header: X-API-Key: <key>
    2. Query parameter: ?api_key=<key>

    Public endpoints (/, /docs, /health/*) don't require authentication.
    """

    def __init__(self, app, api_key: Optional[str] = None):
        super().__init__(app)
        self.api_key = api_key or os.getenv(API_KEY_ENV)

        if not self.api_key:
            logger.warning(
                f"⚠️  No API key configured ({API_KEY_ENV}). "
                "API will be accessible without authentication!"
            )

    async def dispatch(self, request: Request, call_next: Callable):
        # Allow CORS preflight requests through without authentication
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path.rstrip("/")

        # Allow public paths without authentication
        if self._is_public_path(path):
            return await call_next(request)

        # If no API key configured, allow all requests (dev mode)
        if not self.api_key:
            return await call_next(request)

        # Check for API key in request
        provided_key = self._extract_api_key(request)

        if not provided_key:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "API key required",
                    "hint": "Provide API key via 'X-API-Key' header or 'api_key' query parameter",
                },
            )

        if provided_key != self.api_key:
            logger.warning(f"Invalid API key attempt from {request.client.host}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Invalid API key"},
            )

        return await call_next(request)

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (no auth required)."""
        path_normalized = path.rstrip("/")

        # Exact match
        if path_normalized in PUBLIC_PATHS or f"{path_normalized}/" in PUBLIC_PATHS:
            return True

        # Health endpoints are public
        if path_normalized.startswith("/health"):
            return True

        return False

    def _extract_api_key(self, request: Request) -> Optional[str]:
        """Extract API key from request headers or query params."""
        # Try header first (preferred)
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key

        # Fallback to query parameter
        api_key = request.query_params.get("api_key")
        return api_key


def get_api_key_from_env() -> Optional[str]:
    """Get API key from environment variable."""
    return os.getenv(API_KEY_ENV)
