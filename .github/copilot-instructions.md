# Library Portal API - Copilot Instructions

## Project Overview

This is a FastAPI-based REST API for serving MIT Library Question Papers. The API provides organized access to question papers with filtering, search, and metadata capabilities. It includes an automated scraper that runs weekly to fetch new papers.

**Key Features:**
- FastAPI backend with Pydantic models
- API key authentication for protected endpoints
- Fuzzy search capabilities using TheFuzz
- Automated scraping with Scrapy (2025+ papers only)
- Automated categorization and data validation
- Deployed on Render free tier

## Project Structure

```
library-portal-api/
├── app_v2/                 # Main FastAPI application
│   ├── main.py            # Application entry point
│   ├── data_loader.py     # Multi-file JSON data loader
│   ├── models.py          # Pydantic models
│   ├── routes/            # API endpoint routers
│   ├── services/          # Business logic (indexing, search)
│   └── middleware/        # Authentication middleware
├── config/                # Configuration and settings
│   └── config_v2.py       # Pydantic settings with env support
├── data/classified/organized/  # Categorized paper data (JSON)
│   ├── btech/             # BTech papers by branch
│   ├── masters/           # Masters programs (MTech, MCA, ME)
│   ├── bsc/               # BSc programs
│   └── other.json         # Uncategorized papers
├── scraper/               # Scrapy-based web scraper
│   ├── library_scraper/   # Scrapy spider
│   ├── scraper_config.py  # Scraper configuration
│   └── scrape_log.json    # Scraping history log
├── scripts/               # Utility scripts
│   ├── add_program_abbrev.py   # Add/update program_abbrev field
│   └── processing/        # Data processing scripts
│       ├── paper_categorizer.py    # Categorization logic
│       ├── validate_data.py        # Data integrity checks
│       ├── run_categorizer.py      # Categorizer runner
│       └── staging_handler.py      # Manual review queue
├── staging/               # Papers pending manual review
├── docs/                  # Documentation
└── .github/workflows/     # GitHub Actions workflows
    └── scraper-v2.yml     # Weekly scraper automation
```

## Development Setup

### Prerequisites
- Python 3.11+ (tested with 3.12)
- pip for dependency management

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the API locally
uvicorn app_v2.main:app --reload --port 8000

# Access the API documentation
# Swagger UI: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc

# Test the health endpoint
curl http://localhost:8000/health
```

### Running Tests and Validation

```bash
# Validate data integrity
python scripts/processing/validate_data.py

# Format code (before committing)
black .

# Manual scraper run (for testing)
cd scraper && scrapy crawl question_papers_enhanced
```

## Coding Conventions

### Python Style
- **Use Black formatter** for code formatting (already configured)
- Follow PEP 8 style guidelines
- Use type hints for function parameters and return values
- Use Pydantic models for data validation and serialization

### Code Organization
- Keep routes in `app_v2/routes/` directory, organized by resource
- Business logic goes in `app_v2/services/`
- Middleware components in `app_v2/middleware/`
- Configuration uses Pydantic Settings with `LIBRARY_PORTAL_` prefix

### Environment Variables
All environment variables use the `LIBRARY_PORTAL_` prefix:
- `LIBRARY_PORTAL_API_KEY` - API authentication key
- `LIBRARY_PORTAL_ENVIRONMENT` - `development` or `production`
- `LIBRARY_PORTAL_LOG_LEVEL` - `DEBUG`, `INFO`, `WARNING`
- `LIBRARY_PORTAL_CORS_ORIGINS` - Comma-separated allowed origins

Use `.env.development` for local development and `.env.production` for production configuration.

### Logging
- Use Python's standard logging module
- Log level configured via `LIBRARY_PORTAL_LOG_LEVEL`
- Include contextual information in log messages
- Use structured logging format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`

## API Patterns

### Authentication
- Public endpoints: `/`, `/docs`, `/redoc`, `/health`, `/health/data`
- Protected endpoints: All `/api/*` routes
- Authentication via `APIKeyMiddleware`
- Support both header (`X-API-Key`) and query parameter (`api_key`)

### Response Models
- Always use Pydantic models for request/response validation
- Include proper error responses with appropriate HTTP status codes
- Use pagination for list endpoints (default: 50, max: 500)
- Paper responses include `program_abbrev` field for program identification
- Metadata endpoints expose available program abbreviations

### Error Handling
- Return appropriate HTTP status codes (400, 401, 404, 500)
- Include descriptive error messages in response body
- Log errors with sufficient context for debugging

## Data Management

### Data Structure
Papers are stored in JSON files organized by program and branch:
- `data/classified/organized/btech/branches/{branch}.json`
- `data/classified/organized/btech/first_year/{stream}.json`
- `data/classified/organized/masters/{program}.json`
- `data/classified/organized/bsc/{program}.json`
- `data/classified/organized/other.json`

Each paper object includes a `program_abbrev` field containing a short abbreviation (e.g., "BME", "CSE", "ECE") derived from the program name, filename, or course code. This field enables efficient filtering by program in the API and frontend.

### Data Validation
- Run `python scripts/processing/validate_data.py` before committing data changes
- Ensure JSON files are properly formatted
- Verify all required fields are present in paper objects
- Check for duplicate papers by URL

### Scraper Configuration
- **Target years:** 2025 and newer (configured in `scraper/scraper_config.py`)
- **Blacklisted years:** 2006-2024 (already organized, avoid re-scraping)
- Scraper runs weekly via GitHub Actions (Sunday 2 AM UTC)
- Manual trigger available via workflow_dispatch

### Categorization Logic
First-year papers (2024+) are categorized by stream:
- **CS Stream:** Course codes matching `CSS*` or `XX02` pattern
- **Core/Non-CS Stream:** Course codes matching `XX71` or `XX72` pattern

Other papers are categorized by branch/program based on course code prefixes.

## GitHub Actions Workflow

The repository uses GitHub Actions for automated scraping:
- **Schedule:** Weekly on Sunday at 2 AM UTC
- **Workflow:** `.github/workflows/scraper-v2.yml`
- **Steps:**
  1. Pre-scrape validation (count existing papers)
  2. Run scraper (2025+ papers only)
  3. Categorize new papers
  4. Validate data integrity
  5. Commit changes (if any)
  6. Check staging queue for manual reviews

**Dry run mode:** Available via manual workflow dispatch for testing.

## Deployment

### Render Configuration
- Platform: Render free tier
- Configuration: `render.yaml`
- Web service runs: `gunicorn app_v2.main:app -w 4 -k uvicorn.workers.UvicornWorker`
- Environment variables set via Render dashboard
- Auto-deploys from `main` branch

### Health Checks
- `/health` - Basic health status
- `/health/data` - Data integrity validation
- Used by Render for service health monitoring

## Common Tasks

### Adding a New API Endpoint
1. Create route function in appropriate router file in `app_v2/routes/`
2. Define request/response Pydantic models in `app_v2/models.py`
3. Add business logic to `app_v2/services/` if complex
4. Import and include router in `app_v2/main.py`
5. Test endpoint via Swagger UI at `/docs`
6. Verify authentication if protected endpoint

### Modifying Data Structure
1. Update data loader in `app_v2/data_loader.py`
2. Update Pydantic models in `app_v2/models.py`
3. Update categorization logic in `scripts/processing/paper_categorizer.py`
4. Run validation: `python scripts/processing/validate_data.py`
5. Update API documentation in README.md

### Adding a New Field to Paper Data
1. Create a migration script in `scripts/` directory (e.g., `add_field_name.py`)
2. Implement field derivation logic with multiple fallback strategies
3. Update Pydantic models in `app_v2/models.py` to include the new field
4. Update indexing service in `app_v2/services/indexing.py` if the field needs indexing
5. Update API routes in `app_v2/routes/*.py` to expose the field
6. Run the migration script: `python scripts/add_field_name.py`
7. Validate data: `python scripts/processing/validate_data.py`
8. Update `.github/copilot-instructions.md` to document the new field

**Example:** The `program_abbrev` field was added using `scripts/add_program_abbrev.py` with a 4-priority derivation strategy:
1. Filename-based mapping (for btech/branches)
2. Program/specialization name matching
3. Course code prefix extraction
4. Curriculum context branches (from valid_for_branches field)
- Fallback: "UNKNOWN" if no derivation succeeds

### Updating Scraper Configuration
1. Modify `scraper/scraper_config.py` for target years/blacklist
2. Update spider logic in `scraper/library_scraper/spiders/`
3. Test locally: `cd scraper && scrapy crawl question_papers_enhanced`
4. Verify output in `scraper/scraped_output.json`
5. Run categorizer: `python scripts/processing/run_categorizer.py scraper/scraped_output.json --dry-run`

## Data Migration Patterns

When adding new fields to paper data, follow these patterns:

### Migration Script Structure
- Place scripts in `scripts/` directory
- Use descriptive names: `add_{field_name}.py`
- Include docstring with usage instructions
- Implement robust error handling and logging
- Process all data directories (btech, masters, bsc, other.json)

### Field Derivation Strategy
Use a priority-based approach with multiple fallback sources:
1. **Explicit mappings** - Use predefined dictionaries for known values
2. **Field matching** - Derive from existing fields (program, specialization)
3. **Pattern extraction** - Extract from structured fields (course codes)
4. **Fallback values** - Use safe defaults or existing data

### Example Migration Script
```python
# scripts/add_program_abbrev.py demonstrates this pattern:
import re
from typing import Optional

# Priority 1: Filename-based mapping
FILENAME_TO_ABBREV = {
    "CSE": "CSE",
    "ECE": "ECE",
    # ... more mappings
}

# Priority 2: Program name to abbreviation mapping (see complete mapping in script)
PROGRAM_NAME_TO_ABBREV = {
    "computer science and engineering": "CSE",
    "electronics and communication": "ECE",
    # ... more mappings
}

# Priority 3: Course code prefix mapping (see complete mapping in script)
CODE_PREFIX_TO_ABBREV = {
    "CSE": "CSE",
    "ECE": "ECE",
    # ... more mappings
}

def derive_abbrev(paper: dict, filename_abbrev: Optional[str]) -> str:
    """Derive program abbreviation from paper data using 4-priority strategy."""
    
    # Priority 1: Use filename-based abbreviation
    if filename_abbrev:
        return filename_abbrev
    
    # Priority 2: Match program/specialization field
    program = paper.get("program") or paper.get("specialization") or ""
    if program:
        for name, abbrev in PROGRAM_NAME_TO_ABBREV.items():
            if name in program.lower():
                return abbrev
    
    # Priority 3: Extract from course code prefix
    course_code = paper.get("course_code") or paper.get("subject_code") or ""
    if course_code:
        prefix = re.match(r"^([A-Z]{2,4})", course_code.upper())
        if prefix:
            return CODE_PREFIX_TO_ABBREV.get(prefix.group(1), prefix.group(1))
    
    # Priority 4: Check curriculum context branches (if available)
    curriculum_context = paper.get("curriculum_context")
    if curriculum_context and curriculum_context.get("valid_for_branches"):
        branches = curriculum_context["valid_for_branches"]
        if branches and isinstance(branches, list) and len(branches) > 0:
            return branches[0]
    
    # Fallback: Unknown
    return "UNKNOWN"
```

### After Adding a Field
1. Update `app_v2/models.py` - Add field to Pydantic models
2. Update `app_v2/services/indexing.py` - Add indexing if needed
3. Update `app_v2/routes/*.py` - Expose in API responses
4. Run migration: `python scripts/add_{field_name}.py`
5. Validate: `python scripts/processing/validate_data.py`
6. Test API endpoints to verify field is exposed correctly

## Best Practices

### Before Committing
1. Run Black formatter: `black .`
2. Validate data: `python scripts/processing/validate_data.py`
3. Test affected endpoints locally
4. Check that API still starts: `uvicorn app_v2.main:app`
5. Review staging queue: `staging/pending_review.json`

### Code Review Guidelines
- Keep changes focused and minimal
- Include docstrings for new functions/classes
- Update README.md if adding user-facing features
- Ensure backward compatibility for API endpoints
- Test with both development and production configurations

### Performance Considerations
- Data is loaded once at startup (lifespan manager)
- Use indexing service for fast lookups
- Implement pagination for large result sets
- Cache settings using `@lru_cache`
- Monitor Render free tier limits (512MB RAM)

## API Features

### Program Abbreviation Field
The API includes `program_abbrev` field in all paper objects for program identification:
- **Metadata endpoint** (`/api/metadata`): Returns list of all available program abbreviations
- **Statistics endpoint** (`/api/statistics`): Returns paper counts grouped by program abbreviation
- **Papers endpoint** (`/api/papers`): Each paper includes `program_abbrev` field in the response
- **Common abbreviations**: BME, CSE, ECE, EEE, EIE, ME, MXE, CE, CHE, BIO, AERO, AUTO, IT, MPE, M.Tech, M.E, MCA

**Frontend Usage:** Frontends can filter papers by matching the `program_abbrev` field in the response. The API does not currently support `program_abbrev` as a query parameter - you cannot pass `?program_abbrev=CSE` to the `/api/papers` endpoint. For server-side filtering, use the `program` parameter which supports partial text matching.

### Index Service
The `PaperIndex` service pre-builds indexes for fast lookups:
- `_by_program_abbrev`: Index papers by program abbreviation
- `unique_program_abbrevs`: Set of all unique abbreviations
- `count_by_program_abbrev`: Count papers per abbreviation
- `get_by_program_abbrev(abbrev)`: Retrieve papers for a specific abbreviation

## Troubleshooting

### Common Issues
- **Import errors:** Ensure `sys.path` includes project root
- **Data not loading:** Check `DATA_DIRECTORY` path in config
- **Authentication failing:** Verify `LIBRARY_PORTAL_API_KEY` is set
- **CORS errors:** Update `LIBRARY_PORTAL_CORS_ORIGINS`
- **Scraper not finding papers:** Check year threshold and blacklist
- **Missing program_abbrev:** Run `python scripts/add_program_abbrev.py` to populate field

### Debugging
- Set `LIBRARY_PORTAL_LOG_LEVEL=DEBUG` for verbose logging
- Use FastAPI's `/docs` for interactive API testing
- Check `scraper/scrape_log.json` for scraping history
- Review `staging/pending_review.json` for papers needing manual categorization

## Security Notes
- Never commit API keys or secrets to the repository
- Use environment variables for all sensitive configuration
- API key validation happens in `APIKeyMiddleware`
- CORS is configured to allow all origins by default (tighten in production)
- Run on Render free tier with public endpoints exposed

## Resources
- **Live API:** https://library-portal-api.onrender.com
- **API Docs:** https://library-portal-api.onrender.com/docs
- **Health Check:** https://library-portal-api.onrender.com/health
- **Frontend Integration:** See `docs/FRONTEND_INTEGRATION.md`
- **Archive Docs:** See `docs/archive/` for historical context

## Questions?
When in doubt:
1. Check existing code patterns in similar files
2. Review FastAPI and Pydantic documentation
3. Test changes locally before committing
4. Validate data integrity after modifications
5. Consult README.md for high-level architecture
