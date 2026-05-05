"""
Gzip Response Compression Middleware.

Compresses response bodies larger than 1 KB when the client sends
``Accept-Encoding: gzip`` in the request headers.  Small responses
and requests without ``Accept-Encoding: gzip`` are forwarded unchanged.

Security headers added by outer middlewares (e.g.
:class:`SecurityHeadersMiddleware`) are preserved on compressed
responses.

Middleware order (request flow)::

    RequestID -> SecurityHeaders -> CORS -> APIKey -> RateLimit
      -> Compression -> Metrics -> Routes

Compression is registered *inside* RateLimit so that rate-limited
(429) and auth-failure (401/403) responses are never compressed.
"""

import gzip
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

#: Minimum response body size (bytes) to trigger compression.
MINIMUM_SIZE: int = 1024


class CompressionMiddleware(BaseHTTPMiddleware):
    """
    Gzip compression middleware for HTTP responses.

    Compresses response bodies when:

    * The client sends ``Accept-Encoding`` containing ``gzip``.
    * The uncompressed body is larger than :data:`MINIMUM_SIZE` (1 KB).
    * The response does not already carry a ``Content-Encoding`` header.

    On compressed responses the middleware sets ``Content-Encoding: gzip``,
    updates ``Content-Length`` to the compressed size, and appends
    ``Accept-Encoding`` to the ``Vary`` header.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # --- Gate: does the client accept gzip? ---
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" not in accept_encoding.lower():
            return response

        # --- Gate: already encoded? ---
        if response.headers.get("content-encoding"):
            return response

        # --- Read full body ---
        body_chunks: list[bytes] = []
        async for chunk in response.body_iterator:
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")
            body_chunks.append(chunk)
        body = b"".join(body_chunks)

        # --- Gate: too small to compress? ---
        if len(body) < MINIMUM_SIZE:
            # Rebuild response with the consumed body so the client
            # still receives the correct content.
            return self._rebuild_response(response, body)

        # --- Compress ---
        compressed = gzip.compress(body)

        new_response = self._rebuild_response(response, compressed)
        new_response.headers["content-encoding"] = "gzip"
        new_response.headers["content-length"] = str(len(compressed))

        # Append Accept-Encoding to Vary
        vary = response.headers.get("vary", "")
        if vary:
            if "accept-encoding" not in vary.lower():
                new_response.headers["vary"] = f"{vary}, Accept-Encoding"
        else:
            new_response.headers["vary"] = "Accept-Encoding"

        return new_response

    @staticmethod
    def _rebuild_response(original: Response, body: bytes) -> Response:
        """Create a new Response carrying *original* headers and *body*."""
        # Collect headers we want to forward (exclude body-related ones
        # that Response() will recompute).
        excluded = {"content-length", "transfer-encoding"}
        headers = {
            k: v for k, v in original.headers.items() if k.lower() not in excluded
        }

        return Response(
            content=body,
            status_code=original.status_code,
            headers=headers,
            media_type=original.media_type,
        )
