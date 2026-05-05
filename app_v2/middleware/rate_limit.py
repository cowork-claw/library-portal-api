"""
Rate Limiting Middleware.

Fixed-window rate limiter applied to ``/api/*`` and ``/health/data`` routes.
Public paths (``/``, ``/docs``, ``/redoc``, ``/openapi.json``, ``/health``)
are exempt.

Default: 100 requests per 60-second window per client (identified by API key
or client IP when no key is provided). Returns 429 with ``Retry-After``
header when the limit is exceeded.

Failed requests (401, 403, 404, 422) still count toward the limit.
"""

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Callable

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Paths that are exempt from rate limiting
EXEMPT_PATHS: frozenset[str] = frozenset(
    {"/", "/docs", "/redoc", "/openapi.json", "/health"}
)


def _is_rate_limited_path(path: str) -> bool:
    """Return True if *path* should be rate-limited.

    Rate-limited paths:
      - ``/api/*``
      - ``/health/data``  (and ``/health/data/*``)

    Exempt paths:
      - ``/``, ``/docs``, ``/redoc``, ``/openapi.json``, ``/health``
    """
    if path in EXEMPT_PATHS:
        return False
    if path.startswith("/api"):
        return True
    if path.startswith("/health/data"):
        return True
    return False


@dataclass
class _FixedWindow:
    """Fixed-window rate counter.

    Tracks request count within a rolling time window. When the window
    expires, the counter resets and a new window begins.
    """

    max_requests: int
    window_seconds: int
    count: int = field(init=False)
    window_start: float = field(init=False)

    def __post_init__(self) -> None:
        self.count = 0
        self.window_start = time.monotonic()

    def _reset_if_expired(self) -> None:
        """Reset the window if it has expired."""
        now = time.monotonic()
        if now - self.window_start >= self.window_seconds:
            self.count = 0
            self.window_start = now

    def try_consume(self) -> bool:
        """Try to record one request. Returns True if allowed."""
        self._reset_if_expired()
        if self.count < self.max_requests:
            self.count += 1
            return True
        return False

    @property
    def retry_after_seconds(self) -> int:
        """Seconds remaining until the current window resets."""
        now = time.monotonic()
        elapsed = now - self.window_start
        remaining = self.window_seconds - elapsed
        if remaining <= 0:
            return 1
        return max(1, math.ceil(remaining))


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-client fixed-window rate limiter.

    Clients are identified by the ``X-API-Key`` header value when present,
    otherwise by their source IP address.

    Args:
        app: The ASGI application to wrap.
        max_requests: Maximum requests allowed per window (default 100).
        window_seconds: Window duration in seconds (default 60).
    """

    def __init__(
        self,
        app,
        max_requests: int = 100,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # client_id → FixedWindow
        self._windows: dict[str, _FixedWindow] = {}

    async def dispatch(self, request: Request, call_next: Callable):
        # Allow CORS preflight without rate limiting
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # Exempt public paths
        if not _is_rate_limited_path(path):
            return await call_next(request)

        # Identify client
        client_id = self._identify_client(request)

        # Check rate limit
        window = self._get_or_create_window(client_id)

        if not window.try_consume():
            retry_after = window.retry_after_seconds
            logger.warning(
                "Rate limit exceeded for client %s on %s", client_id, path
            )
            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )
            return response

        return await call_next(request)

    def _identify_client(self, request: Request) -> str:
        """Identify a client by API key header or source IP."""
        api_key = request.headers.get("X-API-Key", "").strip()
        if api_key:
            return f"key:{api_key}"
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"

    def _get_or_create_window(self, client_id: str) -> _FixedWindow:
        """Get or create a fixed window for the given client."""
        if client_id not in self._windows:
            self._windows[client_id] = _FixedWindow(
                max_requests=self.max_requests,
                window_seconds=self.window_seconds,
            )
        return self._windows[client_id]
