# Library Portal API V2 - AGENTS

## Project Overview
FastAPI service that serves MIT Library question papers from organized JSON data.
Key paths: `app_v2/` (API), `scraper/` (Scrapy crawler), `data/` (organized papers).

## Critical Behavior (recent PR context)
- **Auth safety**: Only `/`, `/docs`, `/redoc`, `/openapi.json`, and `/health` are public.
  `/health/data` and all `/api/*` routes require `X-API-Key`.
- **Search**: Fuzzy matching uses `rapidfuzz.WRatio` for optimal performance.
- **Filtering**: `/api/papers` uses URL-set intersections from `PaperIndex` for performance.
- **Pagination**: Standardized helper in `app_v2/routes/papers.py`.
- **Security headers**: `SecurityHeadersMiddleware` wraps auth so 401/403 responses include headers.

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
