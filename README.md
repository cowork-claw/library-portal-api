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

## Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/papers` | List papers with filters |
| `GET /api/papers?year=2024&semester=3` | Filter by year/semester |
| `GET /api/papers?course_code=CSE2101` | Filter by course |
| `GET /api/papers?search=algorithms` | Fuzzy search |
| `GET /api/metadata` | Available filter values |
| `GET /api/statistics` | Collection statistics |
| `GET /health` | System health |
| `GET /health/data` | Data integrity |

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

**Generate API key**:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LIBRARY_PORTAL_API_KEY` | API authentication key | **Required in Prod** / Optional in Dev |
| `LIBRARY_PORTAL_ENVIRONMENT` | `development` or `production` | development |
| `LIBRARY_PORTAL_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` | INFO |
| `LIBRARY_PORTAL_CORS_ORIGINS` | Comma-separated origins | * |

## Security

- **Authentication**: `LIBRARY_PORTAL_API_KEY` is **mandatory** in production. The server will refuse requests if it is missing.
- **Fail-Safe**: In development mode, missing API key will trigger a warning but allow access for testing.
- **Dependencies**: Regular security updates are applied.

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

The scraper runs weekly via GitHub Actions, fetching new papers (2025+).

```bash
# Manual run
cd scraper && scrapy crawl question_papers_enhanced
```

Configuration: `scraper/scraper_config.py`

- Target: 2025+ papers only
- Blacklist: 2006-2024 (already organized)

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
python scripts/processing/validate_data.py

# Format code
black .
```

## License

Private repository - internal use only.
