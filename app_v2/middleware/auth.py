"""
API Authentication Middleware for Library Portal V2

Protects API endpoints with API key authentication.
Public endpoints (health, docs) are accessible without authentication.
"""

import logging
import os
import secrets
from typing import Callable, Optional

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Environment variables for API keys
API_KEY_ENV = "LIBRARY_PORTAL_API_KEY"
OPENCLAW_BOT_API_KEY_ENV = "LIBRARY_PORTAL_OPENCLAW_BOT_API_KEY"

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
        configured_keys: list[str] = []

        # Explicitly injected key (used in tests/local wiring)
        if api_key:
            configured_keys.append(api_key)

        # Primary API key
        primary_env_key = os.getenv(API_KEY_ENV)
        if primary_env_key:
            configured_keys.append(primary_env_key)

        # Dedicated bot key
        bot_env_key = os.getenv(OPENCLAW_BOT_API_KEY_ENV)
        if bot_env_key:
            configured_keys.append(bot_env_key)

        # Deduplicate while preserving insertion order
        self.api_keys = list(dict.fromkeys(configured_keys))
        self.environment = environment

        if not self.api_keys:
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

    def _missing_configuration_response(self) -> JSONResponse:
        """Return the non-development response for absent server API keys."""
        logger.error("Blocked request due to missing API key configuration")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Server security misconfiguration",
                "hint": "API Key is required in this environment",
            },
        )

    def _missing_api_key_response(self) -> JSONResponse:
        """Return the response for protected requests without an API key."""
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "detail": "API key required",
                "hint": "Provide API key via 'X-API-Key' header",
            },
        )

    def _invalid_api_key_response(self, request: Request) -> JSONResponse:
        """Log and return the response for an invalid API key."""
        client_host = request.client.host if request.client else "unknown"
        logger.warning(f"Invalid API key attempt from {client_host}")
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Invalid API key"},
        )

    def _is_valid_api_key(self, provided_key: str) -> bool:
        """Return whether a provided key matches any configured key."""
        return any(
            secrets.compare_digest(provided_key, configured_key)
            for configured_key in self.api_keys
        )

    async def dispatch(self, request: Request, call_next: Callable):
        if request.method == "OPTIONS" or self._is_public_path(request.url.path):
            return await call_next(request)

        if not self.api_keys:
            if self.environment == "development":
                return await call_next(request)
            return self._missing_configuration_response()

        provided_key = self._extract_api_key(request)
        if not provided_key:
            return self._missing_api_key_response()

        if not self._is_valid_api_key(provided_key):
            return self._invalid_api_key_response(request)
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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=(), xr-spatial-tracking=()"
        )

        if request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' https://fastapi.tiangolo.com https://cdn.jsdelivr.net data:; "
                "connect-src 'self' https://cdn.jsdelivr.net; "
                "object-src 'none'; "
                "frame-src 'none'; "
                "upgrade-insecure-requests"
            )
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "img-src 'self' https://libportal.manipal.edu data:; "
                "object-src 'none'; "
                "frame-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "upgrade-insecure-requests"
            )

        return response
