"""
Request ID Middleware.

Generates a UUID4 request ID when X-Request-ID header is absent,
preserves the client-provided ID when present, and echoes it back
in the response headers.

Must be registered as the outermost middleware (added last in main.py)
so that all responses—including error responses from inner middlewares—
carry the X-Request-ID header.
"""

import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

HEADER_NAME = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures every request/response cycle carries an
    ``X-Request-ID`` header.

    * If the incoming request already has a non-empty ``X-Request-ID``,
      the value is preserved and echoed back.
    * Otherwise a new UUID4 is generated and set on the response.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Determine request ID: use client value or generate one
        request_id = request.headers.get(HEADER_NAME, "").strip()
        if not request_id:
            request_id = str(uuid.uuid4())

        # Store in request state so downstream code can access it
        request.state.request_id = request_id

        # Proceed through the middleware chain
        response = await call_next(request)

        # Echo the request ID back in the response
        response.headers[HEADER_NAME] = request_id

        return response
