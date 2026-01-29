"""
Prometheus Metrics Middleware.

Collects basic request count and latency metrics.
Enabled only when METRICS_ENABLED is true.
"""

import time
from typing import Callable

from fastapi import Request, Response
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "route", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route"],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to record request count and duration."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)

        REQUEST_COUNT.labels(
            method=request.method,
            route=route_path,
            status_code=str(response.status_code),
        ).inc()
        REQUEST_LATENCY.labels(method=request.method, route=route_path).observe(duration)

        return response
