# Library Portal API V2 - AGENTS

Guidance for AI coding agents and reviewers that operate on this repo (Jules, Codex,
Devin, Kilo, Pullfrog, plus the PR reviewers CodeRabbit, Gemini, Copilot, Qodo, and
Greptile). Review standards are centralized in [REVIEW.md](REVIEW.md).

## Project Overview
FastAPI service (Python 3.12+) serving MIT Library question papers from organized JSON
data. Layered architecture (`routes → services → data_loader`) with `app_v2/main.py`
as the composition root; a separate Scrapy crawler lives in `scraper/`.
~5k LOC, 312 tests, Black + ruff + mypy, deployed on Render.

## Architecture (current)
- `config/config_v2.py` — pydantic `BaseSettings` singleton `settings` (env prefix `LIBRARY_PORTAL_`).
- `app_v2/main.py` — app + lifespan (loads data into the `paper_index` singleton); also defines `/`, `/api`, `/api/metadata`, `/api/statistics`, and optional `/metrics`.
- `app_v2/data_loader.py` — `DataLoader`: loads JSON via orjson, dedups by `url`.
- `app_v2/services/indexing.py` — `PaperIndex`: URL-set indexes, atomic `RLock` reload; extends
- `app_v2/services/index_accessors.py` — `PaperIndexAccessors`: read accessors + `thefuzz` fuzzy search (`@lru_cache`).
- `app_v2/routes/papers.py` — `/api/papers` (filter/search/sort/paginate), `/lookup`, `/year/{year}`, `/course/{code}`, `/semester/{sem}`.
- `app_v2/routes/health.py` — `/health`, `/health/data`, `/health/scraper`, `POST /health/data/reload`.
- `app_v2/middleware/` — `auth.py` (`APIKeyMiddleware` + `SecurityHeadersMiddleware`), `rate_limit.py` (`RateLimitMiddleware`), `structured_logging.py` (`RequestIDMiddleware` + `StructuredLoggingMiddleware`).
- `app_v2/models.py` — pydantic request/response models.
- `scraper/` — Scrapy crawler; `scrape_log.py` exposes the public `normalize_scrape_log_data`, consumed by `routes/health.py` to render `/health/scraper`.

## Critical Behavior (invariants — do not "fix")
- **Auth surface:** only `/`, `/docs`, `/redoc`, `/openapi.json`, `/health` are public (`auth.PUBLIC_PATHS`). `/health/data`, `/health/scraper`, `/metrics`, and all `/api/*` require `X-API-Key`.
- **Middleware order is intentional** (added last = outermost): `RequestID → StructuredLogging → SecurityHeaders → RateLimit → APIKey → CORS → GZip → routes` (plus `Metrics` outermost when `LIBRARY_PORTAL_METRICS_ENABLED`). Do not reorder.
- **Pagination is `limit`/`offset`** — never `page`/`page_size`.
- **Hot reload:** `POST /health/data/reload` returns `202` and, in the background, builds a new `PaperIndex` and swaps it atomically under an `RLock` so in-flight requests are uninterrupted.
- **Filtering/search:** URL-set intersection from `PaperIndex`; fuzzy search is `@lru_cache`-backed in `PaperIndexAccessors`.
- See `docs/ARCHITECTURE.md` for the diagram and `docs/FRONTEND_INTEGRATION.md` for the API contract.

## Commands
```bash
pip install -r requirements.txt          # install
uvicorn app_v2.main:app --reload --port 8000   # run API
pytest -q                                 # tests (312)
black . && ruff check .                   # format + lint
```

## Code Review & Automation
Several bots review PRs here; each reads a specific config. Keep all of them
consistent with [REVIEW.md](REVIEW.md) (the shared standard):

| Reviewer | Config file(s) |
|----------|----------------|
| CodeRabbit (`coderabbitai[bot]`) | `.coderabbit.yaml` (also ingests `AGENTS.md` + `.github/copilot-instructions.md`) |
| Qodo Merge (`qodo-code-review[bot]`) | `.pr_agent.toml` |
| Gemini Code Assist (`gemini-code-assist[bot]`) | `.gemini/config.yaml`, `.gemini/styleguide.md` |
| GitHub Copilot (`copilot-pull-request-reviewer[bot]`) | `.github/copilot-instructions.md` |
| Greptile (`greptile-apps[bot]`) | `greptile.json` |
| Kilo Code Reviews (`kilo-code-bot[bot]`) | `REVIEW.md` |
| Jules / Codex / Devin / Pullfrog | `AGENTS.md` (+ each tool's dashboard settings) |

Jules automations: `.github/workflows/jules-*.yml` (`bug-fixer`, `ci-failure-fixer`,
`paper-classifier`, `performance-agent`, `weekly-cleanup`) and `security-agent.yml`.
They include mechanical pre-check guardrails to avoid duplicate PRs, are scoped to
high-confidence changes only, and do not enforce mandatory doc updates (that caused
merge conflicts). Pullfrog and Devin are configured via their dashboards (no committed
file) but honor `AGENTS.md`/`REVIEW.md` when they run.

## Environment Variables
See `.env.example`. Production must set `LIBRARY_PORTAL_API_KEY`.
Optional: `LIBRARY_PORTAL_SENTRY_DSN` (Sentry), `LIBRARY_PORTAL_METRICS_ENABLED=true` (`/metrics`).

## Repo Structure
- `app_v2/`: FastAPI app (routes, services, middleware, models, data_loader)
- `config/`: settings
- `data/`: organized papers (static JSON)
- `scraper/`: Scrapy pipeline + `scrape_log.py`
- `scripts/`: processing + benchmarks + autoresearch utilities
- `staging/`: manual review queue
- `docs/`: ARCHITECTURE, RUNBOOK, FRONTEND_INTEGRATION, SECURITY_SETUP

## Repo-local Agent Skills
- `worktree-mission-control`: read-only-first git worktree context management with a browser dashboard. Use when worktrees, sandbox branches, copied test repos, or branch confusion are part of the task, or when a new session should reconcile git context before edits.

## Worktree Context Guardrails
- Persist repo-local worktree context in `.agents/state/worktree-viz/`. These artifacts are ephemeral and must stay ignored by Git.
- On a new session, inspect `git worktree list --porcelain`, `git status --short --branch`, `git branch -vv`, `git remote -v`, and `.agents/state/worktree-viz/session-guardrails.json` before editing if any of these are true:
  - more than one worktree exists
  - the active branch is not `main`
  - any worktree is dirty
  - stored guardrails contain pending questions or unresolved conflicts
- If the guardrail flow triggers, run the repo-local `worktree-mission-control` skill in read-only mode first. It should generate `.agents/state/worktree-viz/latest.html`, open it in the default browser, and keep the initial chat summary short.
- During that flow, ask one question at a time and update `.agents/state/worktree-viz/session-guardrails.json` after each answer. Default question order:
  1. Which worktree and branch are the source of truth for this task?
  2. Should the agent remain read-only after review, or may it edit once a worktree is approved?
  3. Which actions or worktrees are forbidden for this task?
  4. Should the answer update long-lived repo guardrails or stay session-local?
- If the current request conflicts with stored guardrails, ask the user which rule wins before editing. Record the resolution in the guardrail state history.
- Default to read-only until the user explicitly authorizes edits. Never create/remove worktrees, delete branches, merge, rebase, prune, or push unless the user explicitly asks for that action.
