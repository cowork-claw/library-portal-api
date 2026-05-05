"""Middleware package for Library Portal API V2."""

from .auth import APIKeyMiddleware, get_api_key_from_env
from .compression import CompressionMiddleware
from .rate_limit import RateLimitMiddleware
from .request_id import RequestIDMiddleware
from .structured_logging import (
    StructuredJSONFormatter,
    StructuredLoggingMiddleware,
    setup_structured_logging,
)

__all__ = [
    "APIKeyMiddleware",
    "CompressionMiddleware",
    "RateLimitMiddleware",
    "StructuredJSONFormatter",
    "StructuredLoggingMiddleware",
    "RequestIDMiddleware",
    "get_api_key_from_env",
    "setup_structured_logging",
]
