"""
Security Headers Middleware.

Adds HTTP headers to enhance security.
"""

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy
        # Disable sensitive features
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=(), xr-spatial-tracking=()"
        )

        # Content Security Policy (CSP)
        # Determine if this is a documentation endpoint
        path = request.url.path
        if path.startswith(("/docs", "/redoc", "/openapi.json")):
            # Relaxed CSP for Swagger UI / ReDoc
            # Allow unsafe-inline for Swagger UI scripts/styles and connections to CDNs
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
            # Strict CSP for API endpoints
            # Restrict content sources to self and trusted domains
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
