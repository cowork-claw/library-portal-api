# Code Review Guide

Shared review standard for **Library Portal API V2**. This is the single source of
truth for how automated reviewers and humans should review pull requests here.

Reviewers that read this file (directly or as a referenced guideline):
Kilo Code Reviews (`review.md`), CodeRabbit, Greptile, Qodo Merge, Gemini Code
Assist, GitHub Copilot, and AGENTS.md-based agents (Jules, Codex, Devin, Pullfrog).
See [AGENTS.md](AGENTS.md) for the reviewer/config map.

## Project snapshot

FastAPI service (Python 3.12+) serving MIT Library question papers from organized
JSON. Layered: `routes → services → data_loader`, with `config` and `middleware`
as leaves and `app_v2/main.py` as the composition root. A separate Scrapy crawler
lives in `scraper/`. ~5k LOC, 312 tests, Black + ruff + mypy, deployed on Render.

## Architecture invariants (do not "fix" these)

- **Middleware order is intentional.** In `app_v2/main.py`, middleware added last is
  outermost. Request flow: `RequestID → StructuredLogging → SecurityHeaders →
  RateLimit → APIKey → CORS → GZip → routes` (plus `Metrics` outermost when
  `LIBRARY_PORTAL_METRICS_ENABLED`). Each position is documented inline. Do not
  suggest reordering.
- **Public paths only:** `/`, `/docs`, `/redoc`, `/openapi.json`, `/health`
  (`auth.PUBLIC_PATHS`). Everything else — `/api/*`, `/health/data`,
  `/health/scraper`, `/metrics` — requires the `X-API-Key` header.
- **Pagination is `limit`/`offset`**, never `page`/`page_size`.
- **`PaperIndex`** (`services/indexing.py`) is a module-level singleton; reload builds
  a new index and swaps it atomically under an `RLock`. Filtering uses URL-set
  intersection; fuzzy search (`thefuzz`) is `@lru_cache`-backed in
  `services/index_accessors.py`.
- **Cross-package contract:** `app_v2/routes/health.py` consumes the public
  `scraper.scrape_log.normalize_scrape_log_data` to render `/health/scraper`. This
  import is deliberate; keep that helper public.

## What to prioritize (in order)

1. **Security** — auth bypass, injection, path traversal, secret/PII exposure,
   information leakage in error messages. Escalate to high severity.
2. **Correctness** — logic errors, wrong return paths, edge cases, race conditions,
   off-by-one, incorrect API usage.
3. **Error handling** — missing handling at I/O boundaries (file/network/JSON),
   over-broad `except` that hides failures, error responses that leak internals.
4. **Type honesty** — annotations that don't match runtime, missing hints on public
   route handlers / service methods.
5. **Tests** — new behavior should have a test; flag untested critical paths.

## Do NOT flag (project conventions)

1. **Dependency versions** — Dependabot manages them. A version present in
   `requirements.txt` is valid; never call it nonexistent or suggest pinning the
   `>=` pydantic/pydantic-settings ranges.
2. **Middleware registration order** — see invariants above.
3. **Speculative refactors** — no renames/restructures without a concrete bug or
   vulnerability. "What if the API served large files?" is out of scope (it serves
   JSON only).
4. **Rate limiter memory** — `_FixedWindow` already prunes/evicts stale entries; do
   not suggest Redis/TTLCache without a demonstrated scaling problem.
5. **Formatting/lint** — Black (line length 88) and ruff own this. Do not restate
   linter findings or comment on formatting.
6. **Underscore-prefixed names** — many cross-module APIs use a leading underscore by
   convention; flag this only under a focused architecture discussion, not per-call.

## Scope

Review production code: `app_v2/`, `config/`, and `tests/`. Treat as out of scope
unless a change clearly touches them or introduces a vulnerability: `data/` (static
JSON), `scraper/` (separate Scrapy project), `scripts/` (utilities), `docs/` and
`*.md`, and CI config under `.github/`.

## Conventions

- snake_case functions/vars, PascalCase classes; absolute imports from `app_v2.*`
  (relative imports inside the package are fine).
- Commands: `pytest -q`, `black .`, `ruff check .`. Verify with tests, not opinions.
