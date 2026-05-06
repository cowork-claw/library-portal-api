# Library Portal API V2 - AGENTS

## Project Overview
FastAPI service that serves MIT Library question papers from organized JSON data.
Key paths: `app_v2/` (API), `scraper/` (Scrapy crawler), `data/` (organized papers).

## Critical Behavior (recent PR context)
- **Auth safety**: Only `/`, `/docs`, `/redoc`, `/openapi.json`, and `/health` are public.
  `/health/data` and all `/api/*` routes require `X-API-Key`.
- **Search**: Fuzzy matching uses `thefuzz.WRatio`. Global search results are cached using `@lru_cache` in `PaperIndex` for instant repeated queries.
- **Filtering**: `/api/papers` uses URL-set intersections from `PaperIndex` for performance.
- **Pagination**: Standardized helper in `app_v2/routes/papers.py`.
- **Security headers**: `SecurityHeadersMiddleware` wraps auth so 401/403 responses include headers.
- **Render previews**: `render.yaml` explicitly disables Render preview environments / PR previews; `.github/workflows/cleanup-deployments.yml` removes stale transient deployment records after PRs close or on scheduled cleanup.

## Jules Workflow Guardrails
Jules agent workflows include mechanical pre-check jobs to prevent duplicate PRs:
- **weekly-cleanup**, **performance**, **security** workflows check for open PRs in the same category before invoking Jules. If one exists, the run is skipped.
- Prompts are scoped to high-confidence changes only. Open-ended sweeps (e.g., "find missing type hints") are not allowed.
- Mandatory documentation update rules have been removed to prevent merge conflicts.
- See `.github/copilot-instructions.md` "Codebase Evolution" for the list of already-completed work.

## Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Run API locally
uvicorn app_v2.main:app --reload --port 8000

# Run tests
pytest -q

# Format
black .
```

## Environment Variables
See `.env.example`. Production must set `LIBRARY_PORTAL_API_KEY`.

## Observability (optional)
- `LIBRARY_PORTAL_SENTRY_DSN` enables Sentry error tracking.
- `LIBRARY_PORTAL_METRICS_ENABLED=true` exposes `/metrics` (Prometheus).

## Repo Structure
- `app_v2/`: FastAPI app, routes, services, middleware
- `config/`: settings
- `data/`: organized papers
- `scraper/`: scraping pipeline
- `scripts/`: processing utilities
- `staging/`: manual review queue

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
