"""Gzip response compression middleware.

Compression is registered inside authentication and rate limiting so
early 401/403/429 responses bypass gzip, while successful route
responses larger than 1 KB can be compressed when clients advertise
``Accept-Encoding: gzip``.
"""

from starlette.middleware.gzip import GZipMiddleware

#: Minimum response body size (bytes) to trigger compression.
MINIMUM_SIZE: int = 1024


class CompressionMiddleware(GZipMiddleware):
    """Starlette gzip middleware configured with this API's size threshold."""

    def __init__(self, app, minimum_size: int = MINIMUM_SIZE) -> None:
        super().__init__(app, minimum_size=minimum_size)
