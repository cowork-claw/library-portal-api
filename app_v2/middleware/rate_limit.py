"""
Rate Limiting Middleware.

Fixed-window rate limiter applied to ``/api/*`` and ``/health/data`` routes.
Public paths (``/``, ``/docs``, ``/redoc``, ``/openapi.json``, ``/health``)
are exempt.

Default: 100 requests per 60-second window per client. Valid configured
API keys receive a non-sensitive fingerprint bucket; unauthenticated and
invalid-key traffic is bucketed by client IP so bogus key rotation cannot
bypass failed-auth throttling. Returns 429 with ``Retry-After`` header when
the limit is exceeded.

Failed requests (401, 403, 404, 422) still count toward the limit.
"""

import hashlib
import logging
import math
import secrets
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable

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
    last_seen: float = field(init=False)

    def __post_init__(self) -> None:
        now = time.monotonic()
        self.count = 0
        self.window_start = now
        self.last_seen = now

    def _reset_if_expired(self, now: float) -> None:
        """Reset the window if it has expired."""
        if now - self.window_start >= self.window_seconds:
            self.count = 0
            self.window_start = now

    def try_consume(self, now: float | None = None) -> bool:
        """Try to record one request. Returns True if allowed."""
        now = now or time.monotonic()
        self.last_seen = now
        self._reset_if_expired(now)
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

    Clients with a configured valid API key are identified by a stable hash
    fingerprint. Missing or invalid keys are identified by source IP address.

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
        valid_api_keys: Iterable[str] | None = None,
        max_clients: int = 10000,
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self._valid_api_keys = tuple(key for key in valid_api_keys or () if key)
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
        now = time.monotonic()
        window = self._get_or_create_window(client_id, now)

        if not window.try_consume(now):
            retry_after = window.retry_after_seconds
            logger.warning("Rate limit exceeded for client %s on %s", client_id, path)
            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )
            return response

        return await call_next(request)

    def _identify_client(self, request: Request) -> str:
        """Identify a client without storing or logging raw credentials."""
        api_key = request.headers.get("X-API-Key", "").strip()
        if api_key and self._is_configured_key(api_key):
            fingerprint = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
            return f"key:{fingerprint}"
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"

    def _is_configured_key(self, api_key: str) -> bool:
        """Return True only for API keys this middleware was configured to trust."""
        return any(secrets.compare_digest(api_key, key) for key in self._valid_api_keys)

    def _get_or_create_window(self, client_id: str, now: float) -> _FixedWindow:
        """Get or create a fixed window for the given client."""
        self._prune_windows(now)
        if client_id not in self._windows:
            self._evict_oldest_if_full()
            self._windows[client_id] = _FixedWindow(
                max_requests=self.max_requests,
                window_seconds=self.window_seconds,
            )
        return self._windows[client_id]

    def _prune_windows(self, now: float) -> None:
        """Remove expired or least-recently-seen client windows."""
        expired = [
            client_id
            for client_id, window in self._windows.items()
            if now - window.last_seen >= self.window_seconds
        ]
        for client_id in expired:
            self._windows.pop(client_id, None)

        overflow = len(self._windows) - self.max_clients
        if overflow <= 0:
            return

        oldest_client_ids = sorted(
            self._windows,
            key=lambda client_id: self._windows[client_id].last_seen,
        )[:overflow]
        for client_id in oldest_client_ids:
            self._windows.pop(client_id, None)

    def _evict_oldest_if_full(self) -> None:
        """Make room for a new client when the hard cap is reached."""
        if len(self._windows) < self.max_clients:
            return

        oldest_client_id = min(
            self._windows,
            key=lambda client_id: self._windows[client_id].last_seen,
        )
        self._windows.pop(oldest_client_id, None)
