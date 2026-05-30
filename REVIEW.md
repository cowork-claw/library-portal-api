# REVIEW.md

Shared code-review standard for **Library Portal API V2**. Kilo Code Reviews reads
this file from the pull-request **base branch**; the other reviewers (CodeRabbit,
Greptile, Qodo, Gemini, Copilot) and AGENTS.md-based agents (Jules, Codex, Devin,
Pullfrog) treat it as the single source of truth. See [AGENTS.md](AGENTS.md) for the
reviewer → config-file map.

## What matters in this repository
- FastAPI service (Python 3.12+) serving MIT Library question papers from organized
  JSON. Layered `routes → services → data_loader`; `config` and `middleware` are
  leaves; `app_v2/main.py` is the composition root. A separate Scrapy crawler lives
  in `scraper/`. ~5k LOC, 312 tests, Black + ruff + mypy, Render.
- **Architecture invariants — preserve these; do not "fix" them:**
  - **Middleware order** in `app_v2/main.py` is intentional (added last = outermost):
    `RequestID → StructuredLogging → SecurityHeaders → RateLimit → APIKey → CORS →
    GZip → routes` (plus `Metrics` outermost when `LIBRARY_PORTAL_METRICS_ENABLED`).
    Never suggest reordering.
  - **Auth surface:** only `/`, `/docs`, `/redoc`, `/openapi.json`, `/health` are
    public (`auth.PUBLIC_PATHS`); every other route — `/api/*`, `/health/data`,
    `/health/scraper`, `/metrics` — requires the `X-API-Key` header.
  - **Pagination is `limit`/`offset`**, never `page`/`page_size`.
  - **`PaperIndex`** (`services/indexing.py`) is a module-level singleton; reload
    builds a new index and swaps it atomically under an `RLock`. Filtering is URL-set
    intersection; fuzzy search (`thefuzz`) is `@lru_cache`-backed in
    `services/index_accessors.py`.
  - `app_v2/routes/health.py` consumes the **public**
    `scraper.scrape_log.normalize_scrape_log_data` to render `/health/scraper` — that
    cross-package helper is meant to stay public.
- Prefer small, explicit fixes over broad refactors.

## Severity calibration
- **Critical:** auth bypass, injection, path traversal, secret/PII exposure,
  information leakage in error messages, data loss.
- **Warning:** missing validation at I/O boundaries (file/network/JSON), over-broad
  `except` that hides failures, error responses leaking internals, type annotations
  that don't match runtime, missing tests for new behavior.
- **Do NOT flag:**
  - Dependency versions — Dependabot manages them; never call a pinned version
    invalid or suggest pinning the `>=` pydantic / pydantic-settings ranges.
  - Middleware registration order (see invariants).
  - Speculative refactors/renames without a concrete bug or vulnerability
    ("what if it served large files?" — it serves JSON only).
  - Rate-limiter memory — `_FixedWindow` already prunes/evicts; no Redis/TTLCache
    without a demonstrated scaling problem.
  - Formatting/lint — Black (line length 88) and ruff own this; don't restate.
  - Leading-underscore cross-module names — a deliberate convention here; raise only
    in a focused architecture discussion, not per call site.

## Verification expectations
- New behavior needs a test that asserts the observable result (`pytest -q`, 312 tests).
- Changes to data loading/indexing must preserve URL dedup and the atomic-reload
  (`RLock` swap) semantics.
- Validate with tests, `black .`, and `ruff check .` — not opinions.

## Scope
Review production code: `app_v2/`, `config/`, `tests/`. Treat as out of scope unless a
change clearly touches them or introduces a vulnerability: `data/` (static JSON),
`scraper/`, `scripts/`, `docs/`, `*.md`, and `.github/` CI config.

## Review summary style
Be concise and concrete; only flag issues introduced by the PR. Cite `file:line`,
group findings by severity, and lead with anything Critical. Skip nitpicks.
