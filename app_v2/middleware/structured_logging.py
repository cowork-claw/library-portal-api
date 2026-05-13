"""Structured JSON logging and request ID middleware."""

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

#: Current request ID for log records; ``"-"`` outside request context.
current_request_id: ContextVar[str] = ContextVar("current_request_id", default="-")
HEADER_NAME = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Ensure every response carries an X-Request-ID header."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get(HEADER_NAME, "").strip()
        if not request_id:
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[HEADER_NAME] = request_id
        return response


class RequestIDLogFilter(logging.Filter):
    """Inject the current request ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id.get("-")
        return True


class StructuredJSONFormatter(logging.Formatter):
    """Serialize each log record as one JSON object."""

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


_access_logger = logging.getLogger("app_v2.access")
_STRUCTURED_HANDLER_MARKER = "_library_portal_structured_handler"


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Set request ID logging context and emit access log records."""

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


def setup_structured_logging(level: str = "INFO") -> None:
    """Configure the root logger with this module's JSON stdout handler."""
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
