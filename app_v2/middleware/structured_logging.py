"""
Structured JSON Logging Middleware.

When active, configures the Python logging system to emit structured JSON
log lines containing ``timestamp``, ``level``, ``name``, ``message``, and
``request_id`` fields.  Integrates with :class:`RequestIDMiddleware` via a
:class:`~contextvars.ContextVar` so every log line emitted during a request
carries the current request's ID.

Usage::

    from app_v2.middleware.structured_logging import (
        StructuredLoggingMiddleware,
        setup_structured_logging,
    )

    # Configure the root logger (call once at startup)
    setup_structured_logging("INFO")

    # Register middleware inside RequestIDMiddleware so it can read
    # request.state.request_id
    app.add_middleware(StructuredLoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)  # outermost
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# ---------------------------------------------------------------------------
# Context variable
# ---------------------------------------------------------------------------

#: Holds the current request ID (populated by this middleware from
#: ``request.state.request_id``, which is set by ``RequestIDMiddleware``).
#: Falls back to ``"-"`` outside of a request context.
current_request_id: ContextVar[str] = ContextVar("current_request_id", default="-")


# ---------------------------------------------------------------------------
# Logging filter
# ---------------------------------------------------------------------------


class RequestIDLogFilter(logging.Filter):
    """
    Logging filter that injects the current ``request_id`` from the
    :data:`current_request_id` context variable into every log record.

    This allows the :class:`StructuredJSONFormatter` to include the
    request ID in every log line without requiring loggers to pass it
    explicitly.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id.get("-")
        return True


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------


class StructuredJSONFormatter(logging.Formatter):
    """
    Formatter that serialises each log record as a single-line JSON object.

    Required fields in every line:

    * ``timestamp`` — ISO-8601 with timezone (UTC).
    * ``level`` — Log level name (``INFO``, ``WARNING``, …).
    * ``name`` — Logger name.
    * ``message`` — Formatted message string.
    * ``request_id`` — Current request ID or ``"-"`` if outside a request.

    Additional fields (``method``, ``path``, ``status_code``) are included
    when present on the log record (set by the access-log emission in
    :class:`StructuredLoggingMiddleware`).
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }

        # Include access-log extras when present
        for field in ("method", "path", "status_code"):
            value = getattr(record, field, None)
            if value is not None:
                log_entry[field] = value

        # Append exception traceback when present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

_access_logger = logging.getLogger("app_v2.access")
_STRUCTURED_HANDLER_MARKER = "_library_portal_structured_handler"


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that bridges the request context into the logging system.

    On each request it:

    1. Reads ``request.state.request_id`` (set by :class:`RequestIDMiddleware`).
    2. Stores it in the :data:`current_request_id` context variable so that
       :class:`RequestIDLogFilter` can inject it into every log record.
    3. After the response is produced, emits an *access log* line to the
       ``app_v2.access`` logger containing ``method``, ``path``, and
       ``status_code``.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Propagate request ID into the logging context var
        request_id = getattr(request.state, "request_id", "-")
        token = current_request_id.set(request_id)

        try:
            response = await call_next(request)

            # Emit access log with request metadata
            _access_logger.info(
                "%s %s %s",
                request.method,
                request.url.path,
                response.status_code,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                },
            )

            return response
        finally:
            current_request_id.reset(token)


# ---------------------------------------------------------------------------
# Setup helper
# ---------------------------------------------------------------------------


def setup_structured_logging(level: str = "INFO") -> None:
    """
    Configure the root Python logger for structured JSON output.

    Adds one owned :class:`~logging.StreamHandler` writing to *stdout*, using
    :class:`StructuredJSONFormatter` and :class:`RequestIDLogFilter`. Existing
    root handlers are left in place so server/test logging configuration is
    not unexpectedly removed at import time.

    Args:
        level: Logging level name (e.g. ``"INFO"``, ``"DEBUG"``).
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    for handler in root_logger.handlers:
        if getattr(handler, _STRUCTURED_HANDLER_MARKER, False):
            handler.setLevel(getattr(logging, level.upper(), logging.INFO))
            return

    # Create and attach the structured handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJSONFormatter())
    handler.addFilter(RequestIDLogFilter())
    setattr(handler, _STRUCTURED_HANDLER_MARKER, True)
    root_logger.addHandler(handler)
