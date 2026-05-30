# Library Portal API V2 - Code Review Style Guide

This guide instructs Gemini Code Assist on how to review code in this repository.

## Project Overview

FastAPI service serving MIT Library question papers from organized JSON data.
Python 3.12+, Black formatter, ruff linter, pytest test suite, mypy type checking.
Deployed on Render with Sentry error tracking (optional).

## Architecture

The application follows a layered architecture in `app_v2/`:

- **Routes** (`routes/`): FastAPI routers for papers, metadata, health endpoints.
- **Services** (`services/indexing.py`): `PaperIndex` singleton with `@lru_cache`-backed
  fuzzy search and URL-set intersection filters for performance.
- **Middleware** (`middleware/`): Stacked in a specific order (see below).
- **Data loader** (`data_loader.py`): Loads JSON files from the `data/` directory.

Only `/`, `/docs`, `/redoc`, `/openapi.json`, and `/health` are public.
All `/api/*` and `/health/data` routes require `X-API-Key` authentication.

## Middleware Stack Ordering

The middleware registration order in `main.py` is **intentional and must not be
changed**. In FastAPI, middleware added last executes first (outermost). The
current stack from outermost to innermost is:

1. **RequestIDMiddleware** (outermost) — assigns `X-Request-ID` to every request
2. **StructuredLoggingMiddleware** — JSON access logs, reads `request.state.request_id`
3. **SecurityHeadersMiddleware** — adds security headers, wraps auth so 401/403
   responses include headers
4. **RateLimitMiddleware** — throttles `/api/*` and `/health/data`, wraps APIKey so
   failed auth counts toward the rate limit
5. **APIKeyMiddleware** — validates `X-API-Key` on protected routes
6. **CORSMiddleware** — standard CORS handling
7. **GZipMiddleware** (innermost) — only compresses successful route responses;
   auth/rate-limit errors are generated further out and never reach this layer

**Do NOT suggest reordering middleware.** Each layer's position is documented and
intentional. The compression middleware being innermost is a deliberate choice so
that error responses (401, 403, 429) are never compressed.

## Review Focus Areas

Prioritize reviews in this order:

1. **Security vulnerabilities**: Injection, auth bypass, sensitive data exposure,
   insecure defaults, missing input validation. Always escalate these to HIGH
   severity regardless of the default severity rating.
2. **Correctness bugs**: Logic errors, race conditions, incorrect API usage,
   off-by-one errors, unhandled edge cases.
3. **Error handling**: Missing exception handling, improper error responses,
   information leakage in error messages.

## Anti-Patterns (Do NOT Flag These)

1. **Dependency versions**: Never flag package version numbers as invalid or
   non-existent on PyPI. Dependabot manages all dependency updates. If a version
   appears in `requirements.txt`, assume it is valid and available.
2. **Middleware registration order**: See above. The order is intentional with
   inline comments explaining the design. Do not suggest reordering.
3. **Architectural suggestions without a concrete bug**: Do not suggest refactoring,
   renaming, or restructuring code unless you can identify a specific bug or
   security vulnerability. Style preferences, hypothetical future concerns ("what
   if the API serves large files?"), and speculative performance issues are not
   actionable for this project.
4. **Pydantic version pinning**: This project intentionally uses `>=` version ranges
   for pydantic and pydantic-settings. Do not suggest pinning to exact versions.
5. **Rate limiter memory management**: The `_FixedWindow` cleanup logic with
   `_prune_windows()` and `_evict_oldest_if_full()` already handles stale entries
   and hard-cap eviction. Do not suggest replacing the in-memory store with external
   caches (Redis, TTLCache) unless there is a demonstrated scaling problem.
6. **Compression middleware streaming**: This API exclusively serves JSON payloads.
   Do not suggest streaming compression approaches for hypothetical large-file
   serving scenarios.

## Language Conventions

- **Formatting**: Black (line length 88). Do not comment on formatting.
- **Linting**: ruff with project-specific rules in `ruff.toml`. Do not duplicate
  linter findings.
- **Type hints**: Used throughout. Flag missing type hints only on public API
  boundaries (route handlers, service methods).
- **Imports**: Use absolute imports from `app_v2.*`. Relative imports within the
  package are acceptable.

## What to Skip

- Changes to `data/` (static JSON), `course_images/` (binary assets),
  `scraper/` (separate Scrapy project), `scripts/` (utility scripts).
- Documentation changes (`docs/`, `*.md`, `droid-wiki/`).
- CI/CD configuration (`.github/`) unless you spot a security vulnerability.
- Dependency version bumps in `requirements.txt` (Dependabot handles these).
