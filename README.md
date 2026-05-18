# Library Portal API V2

Fast, modern API for MIT Library Question Papers. Built with FastAPI, optimized for Render deployment.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
uvicorn app_v2.main:app --reload --port 8000

# Open docs
open http://localhost:8000/docs
```

## API Authentication

Protected endpoints require an API key:

```bash
# Header (recommended)
curl -H "X-API-Key: your-key" http://localhost:8000/api/papers
```

**Public endpoints** (no auth required):

- `/` - API info
- `/docs` - Swagger UI
- `/health` - Health checks

`/health/data` requires the same API key as other non-public operational endpoints.

## Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/papers` | List papers with filters |
| `GET /api/papers?year=2024&semester=3` | Filter by year/semester |
| `GET /api/papers?course_code=CSE2101` | Filter by course |
| `GET /api/papers?program_abbrev=CSE` | Filter by program abbreviation (case-insensitive, composes with other filters) |
| `GET /api/papers?search=algorithms` | Fuzzy search |
| `GET /api/papers?sort=year&order=desc` | Sort by `year`, `semester`, or `relevance` (asc/desc) |
| `GET /api/papers/lookup?url=<paper_url>` | Look up a single paper by its download URL |
| `GET /api/metadata` | Available filter values |
| `GET /api/statistics` | Collection statistics |
| `GET /health` | System health |
| `GET /health/data` | Data integrity |
| `POST /health/data/reload` | Admin endpoint to reload data without restarting (returns `202 Accepted` with `reload_id`) |

## Data Structure

```
data/classified/organized/
├── btech/
│   ├── branches/       # CSE.json, ECE.json, etc.
│   └── first_year/     # cs_stream.json, non_cs_stream.json
├── masters/            # mtech.json, mca.json, me.json
├── bsc/                # icas.json
└── other.json
```

**Total**: 777 papers, 343 courses, 23 files

## Deployment (Render)

1. Connect GitHub repo to Render
2. Set environment variables:

   ```
   LIBRARY_PORTAL_API_KEY=<generate-secure-key>
   LIBRARY_PORTAL_ENVIRONMENT=production
   ```

3. Deploy - uses `render.yaml` automatically

### Notes on PR Deployments vs CI

- **GitHub Actions CI already exists** in `.github/workflows/ci.yml` and runs tests/lint checks for PRs and pushes to `main`.
- **GitHub deployment entries are different from CI checks.** In this repo, those deployment records are created by the **Render GitHub App** when Render preview deployments are enabled for PR branches.
- `render.yaml` now declares `previews.generation: off` and `pullRequestPreviewsEnabled: false` so the repo configuration matches the desired "main-only" deployment behavior.
- If Render still shows PR previews after syncing the Blueprint, disable **Preview Environments** / **PR Previews** once in the Render dashboard for the existing service so dashboard state matches the repo config.
- This repo includes `.github/workflows/cleanup-deployments.yml` to clean up stale transient PR deployment records after PRs close and on scheduled/manual cleanup runs.

**Generate API key**:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LIBRARY_PORTAL_API_KEY` | API authentication key | **Required in Prod** / Optional in Dev |
| `LIBRARY_PORTAL_OPENCLAW_BOT_API_KEY` | Optional secondary API key for OpenClaw bot access | empty (disabled) |
| `LIBRARY_PORTAL_ENVIRONMENT` | `development` or `production` | development |
| `LIBRARY_PORTAL_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` | INFO |
| `LIBRARY_PORTAL_CORS_ORIGINS` | Comma-separated origins | * |
| `LIBRARY_PORTAL_SENTRY_DSN` | Sentry DSN for error tracking | empty (disabled) |
| `LIBRARY_PORTAL_SENTRY_TRACES_SAMPLE_RATE` | Sentry tracing sample rate | 0.0 |
| `LIBRARY_PORTAL_METRICS_ENABLED` | Enable `/metrics` endpoint | false |

## Security

- **Authentication**: `LIBRARY_PORTAL_API_KEY` is **mandatory** in production. The server will refuse requests if it is missing.
- **Rate Limiting**: Fixed-window rate limiter (100 req/min per client) on `/api/*` and `/health/data`. Returns `429 Too Many Requests` with `Retry-After` header when exceeded.
- **Request ID Tracking**: Every request carries an `X-Request-ID` header. If not provided by the client, a UUID4 is auto-generated and echoed back in the response for traceability.
- **Input Validation**: Strict type and length checking on all API parameters to prevent DoS and Injection attacks. Added `max_length` validation to course code endpoint.
- **Path Sanitization**: Internal file paths are stripped from error messages and API responses to prevent information disclosure.
- **Performance / Responsiveness**: Offloaded synchronous I/O operations (file reading and JSON parsing) in health routes to a threadpool via `run_in_threadpool` to prevent event loop blocking.
- **Fail-Safe**: In development mode, missing API key will trigger a warning but allow access for testing.
- **Dependencies**: Regular security updates are applied.

> ⚡ **Jules Security Tip:** For proactive security scanning, adhere to the [Copilot coding agent tips](https://gh.io/copilot-coding-agent-tips).

## Observability

- **Structured JSON Logging:** When `LIBRARY_PORTAL_LOG_LEVEL` is set, all log output is formatted as structured JSON. Every log line includes a `request_id` field propagated from the `X-Request-ID` header, making it easy to trace requests across logs.
- **Request ID Propagation:** The `X-Request-ID` header is generated (if missing) and echoed on every response. It is also injected into the logging context so that every log record emitted during a request carries the same ID.

## Reliability

- **Graceful Degradation:** The API starts successfully even if the `data/` directory is missing or corrupt. In this case, it serves empty results and the health endpoint reports `degraded` status instead of failing to start.
- **Hot Data Reload:** `POST /health/data/reload` allows admins to reload JSON data without restarting the service. It returns `202 Accepted` with a unique `reload_id` and swaps the index atomically so in-flight requests are not interrupted.

## Performance Optimizations

- **Gzip Compression:** Responses larger than 1 KB are automatically gzip-compressed when the client sends `Accept-Encoding: gzip`. Small responses and error responses (401, 403, 429) are forwarded unchanged.
- **URL Deduplication:** The data loader (`app_v2/data_loader.py`) uses a `set` (`seen_urls`) instead of a `dict` for URL deduplication during the parsing of JSON files. This O(1) membership checking reduces memory overhead and improves data loading speed at startup.
- **Search Filter Optimization:** Filter URL sets are sorted by size before intersection for ~35-50% speedup. Early exits on empty filter sets provide O(1) response time for queries with non-existent filters.
- **Sorting Optimization:** Papers can be sorted by `year`, `semester`, or `relevance` in ascending or descending order. Null values are consistently placed last regardless of sort direction.
- **Health I/O Optimization:** Synchronous file I/O in health check endpoints is offloaded to a threadpool to avoid blocking the event loop.

> ⚡ **Jules Performance Tip:** For optimizations, follow the "Turbo" methodology and reference [Copilot coding agent tips](https://gh.io/copilot-coding-agent-tips) for better collaboration.

## Codebase Cleanup Notes

- **Dead Code Removal:** Removed unused `StagedPaper` dataclass and unused methods from `staging_handler.py`, `scrape_log.py`, `scraper_config.py`, and `config_v2.py`. Added missing return type hints to API endpoints. Applied `black` and `ruff`. Refer to [Copilot agent tips](https://gh.io/copilot-coding-agent-tips) for continuous code cleanup strategies.

## Project Structure

```
lib-portal-master/
├── app_v2/             # API application
│   ├── main.py         # FastAPI app
│   ├── data_loader.py  # Multi-file loader
│   ├── models.py       # Pydantic models
│   ├── routes/         # API endpoints
│   ├── services/       # Indexing, search
│   └── middleware/     # Authentication
├── config/             # Configuration
├── data/               # Organized paper data
├── scraper/            # Paper scraper
├── scripts/processing/ # Categorization
└── staging/            # Manual review queue
```

## Scraper

The scraper runs weekly via GitHub Actions, fetching new papers (2024+).

```bash
# Manual run
cd scraper && scrapy crawl question_papers_enhanced
```

Configuration: `config/config_v2.py` (`TARGET_YEAR_THRESHOLD`, `BLACKLISTED_YEARS`)

- Target: 2024+ papers only
- Blacklist: 2006-2023 (already organized)

## Categorization Logic

### First Year (2024+)

| Stream | Pattern | Example |
|--------|---------|---------|
| **CS** | `CSS*`, `XX02` | `CSS1001`, `MAT1102` |
| **Core** | `XX71/72` | `MAT1171`, `PHY1071` |

See [docs/archive/REMOVED_SCRIPTS_LOG.md](docs/archive/REMOVED_SCRIPTS_LOG.md) for full categorization logic.

## Development

```bash
# Activate venv
source .venv/bin/activate

# Run tests
pytest -q

# Validate data
python scripts/processing/validate_data.py

# Format code
black .
```

## Performance Benchmarking

To measure the performance of key endpoints and optimizations:

```bash
# Run year filter benchmark
python scripts/benchmarks/benchmark_year_filter.py



# Run scraper log benchmark
python scripts/benchmarks/benchmark_scrape_log.py

# Run memory benchmark
python scripts/benchmarks/benchmark_memory.py
```

These scripts measure the performance of key filtering and search logic.

## Docs

- `AGENTS.md` - agent guidance and critical behavior
- `docs/RUNBOOK.md` - operational runbook
- `docs/ARCHITECTURE.md` - service flow diagram
- `docs/SECURITY_SETUP.md` - GitHub security settings checklist

## License

Private repository - internal use only.
