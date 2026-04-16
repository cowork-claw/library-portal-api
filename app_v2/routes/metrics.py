"""
Metrics endpoint.

Exposes Prometheus metrics when METRICS_ENABLED is true.
"""

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(tags=["Metrics"])


@router.get("/metrics")
def metrics() -> Response:
    """
    Expose Prometheus metrics.

    Returns:
        Response: The generated Prometheus metrics in plain text.
    """
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
