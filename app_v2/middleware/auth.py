"""
API Authentication Middleware for Library Portal V2

Protects API endpoints with API key authentication.
Public endpoints (health, docs) are accessible without authentication.
"""

import os
import secrets
from typing import Optional, Callable
from fastapi import Request, status
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
}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware for API key authentication.

    API key must be provided via the 'X-API-Key' header.

    Public endpoints (/, /docs, /health/*) don't require authentication.
    """

    def __init__(
        self, app, api_key: Optional[str] = None, environment: str = "production"
    ):
        super().__init__(app)
        self.api_key = api_key or os.getenv(API_KEY_ENV)
        self.environment = environment

        if not self.api_key:
            if self.environment == "development":
                logger.warning(
                    f"⚠️  No API key configured ({API_KEY_ENV}). "
                    "API will be accessible without authentication (Development Mode Only)!"
                )
            else:
                logger.critical(
                    f"🚨 CRITICAL SECURITY RISK: No API key configured in {self.environment} environment. "
                    "All requests will be blocked."
                )

    async def dispatch(self, request: Request, call_next: Callable):
        # Allow CORS preflight requests through without authentication
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path.rstrip("/")

        # Allow public paths without authentication
        if self._is_public_path(path):
            return await call_next(request)

        # If no API key configured
        if not self.api_key:
            # Only allow in development mode
            if self.environment == "development":
                return await call_next(request)
            else:
                # Block all requests in non-development environments
                logger.error("Blocked request due to missing API key configuration")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "detail": "Server security misconfiguration",
                        "hint": "API Key is required in this environment",
                    },
                )

        # Check for API key in request
        provided_key = self._extract_api_key(request)

        if not provided_key:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "API key required",
                    "hint": "Provide API key via 'X-API-Key' header",
                },
            )

        if not secrets.compare_digest(provided_key, self.api_key):
            logger.warning(f"Invalid API key attempt from {request.client.host}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Invalid API key"},
            )

        return await call_next(request)

    def _is_public_path(self, path: str) -> bool:
        """
        Check if path is public (no auth required).

        Paths are considered public if they are in PUBLIC_PATHS.
        """
        # Normalize path by removing trailing slash for consistent matching
        path_normalized = path.rstrip("/") if path != "/" else "/"

        # Check against the set of defined public paths
        return path_normalized in PUBLIC_PATHS

    def _extract_api_key(self, request: Request) -> Optional[str]:
        """Extract API key from request headers."""
        return request.headers.get("X-API-Key")


def get_api_key_from_env() -> Optional[str]:
    """Get API key from environment variable."""
    return os.getenv(API_KEY_ENV)
