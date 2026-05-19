import hashlib
import logging
import math
import secrets
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


def _is_rate_limited_path(path: str) -> bool:
    return path.startswith("/api") or path.startswith("/health/data")


@dataclass
class _FixedWindow:

    max_requests: int
    window_seconds: int
    count: int = field(default=0, init=False)
    window_start: float = field(default_factory=time.monotonic, init=False)
    last_seen: float = field(init=False)

    def __post_init__(self) -> None:
        self.last_seen = self.window_start

    def _try_consume(self, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        self.last_seen = now
        if now - self.window_start >= self.window_seconds:
            self.count = 0
            self.window_start = now
        if self.count < self.max_requests:
            self.count += 1
            return True
        return False

    @property
    def _retry_after_seconds(self) -> int:
        remaining = self.window_seconds - (time.monotonic() - self.window_start)
        return max(1, math.ceil(remaining))


class RateLimitMiddleware(BaseHTTPMiddleware):

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
        if request.method == "OPTIONS" or not _is_rate_limited_path(request.url.path):
            return await call_next(request)

        path = request.url.path

        # Identify client
        client_id = self._identify_client(request)

        # Check rate limit
        now = time.monotonic()
        window = self._get_or_create_window(client_id, now)

        if not window._try_consume(now):
            logger.warning("Rate limit exceeded for client %s on %s", client_id, path)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(window._retry_after_seconds)},
            )

        return await call_next(request)

    def _identify_client(self, request: Request) -> str:
        api_key = (
            request.headers.get("X-API-Key")
            or request.query_params.get("api_key")
            or ""
        ).strip()
        if api_key and self._is_configured_key(api_key):
            return f"key:{hashlib.sha256(api_key.encode('utf-8')).hexdigest()[:16]}"
        return f"ip:{request.client.host if request.client else 'unknown'}"

    def _is_configured_key(self, api_key: str) -> bool:
        return any(secrets.compare_digest(api_key, key) for key in self._valid_api_keys)

    def _get_or_create_window(self, client_id: str, now: float) -> _FixedWindow:
        self._prune_windows(now)
        if client_id in self._windows:
            return self._windows[client_id]

        if len(self._windows) >= self.max_clients:
            oldest_client_id = min(
                self._windows,
                key=lambda client_id: self._windows[client_id].last_seen,
            )
            self._windows.pop(oldest_client_id, None)
        self._windows[client_id] = _FixedWindow(
            max_requests=self.max_requests,
            window_seconds=self.window_seconds,
        )
        return self._windows[client_id]

    def _prune_windows(self, now: float) -> None:
        for client_id in [
            client_id
            for client_id, window in self._windows.items()
            if now - window.last_seen >= self.window_seconds
        ]:
            self._windows.pop(client_id, None)

        if (overflow := len(self._windows) - self.max_clients) <= 0:
            return

        for client_id in sorted(
            self._windows,
            key=lambda client_id: self._windows[client_id].last_seen,
        )[:overflow]:
            self._windows.pop(client_id, None)
