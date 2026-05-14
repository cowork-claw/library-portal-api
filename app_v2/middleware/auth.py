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
PUBLIC_PATHS = {"/", "/docs", "/redoc", "/openapi.json", "/health"}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=(), usb=(), xr-spatial-tracking=()",
}
DOCS_CSP = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' https://fastapi.tiangolo.com https://cdn.jsdelivr.net data:; connect-src 'self' https://cdn.jsdelivr.net; object-src 'none'; frame-src 'none'; upgrade-insecure-requests"
API_CSP = "default-src 'self'; img-src 'self' https://libportal.manipal.edu data:; object-src 'none'; frame-src 'none'; base-uri 'self'; form-action 'self'; upgrade-insecure-requests"


class APIKeyMiddleware(BaseHTTPMiddleware):

    def __init__(
        self, app, api_key: Optional[str] = None, environment: str = "production"
    ):
        super().__init__(app)
        keys = api_key, os.getenv(API_KEY_ENV), os.getenv(OPENCLAW_BOT_API_KEY_ENV)
        self.api_keys = list(dict.fromkeys(filter(None, keys)))
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

    def _is_valid_api_key(self, provided_key: str) -> bool:
        return any(
            secrets.compare_digest(provided_key, configured_key)
            for configured_key in self.api_keys
        )

    async def dispatch(self, request: Request, call_next: Callable):
        if (
            request.method == "OPTIONS"
            or (request.url.path.rstrip("/") or "/") in PUBLIC_PATHS
        ):
            return await call_next(request)

        if not self.api_keys:
            if self.environment == "development":
                return await call_next(request)
            logger.error("Blocked request due to missing API key configuration")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Server security misconfiguration",
                    "hint": "API Key is required in this environment",
                },
            )

        provided_key = request.headers.get("X-API-Key")
        if not provided_key:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "API key required",
                    "hint": "Provide API key via 'X-API-Key' header",
                },
            )

        if not self._is_valid_api_key(provided_key):
            client_host = request.client.host if request.client else "unknown"
            logger.warning(f"Invalid API key attempt from {client_host}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Invalid API key"},
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        response.headers["Content-Security-Policy"] = (
            DOCS_CSP
            if request.url.path.startswith(("/docs", "/redoc", "/openapi.json"))
            else API_CSP
        )

        return response
