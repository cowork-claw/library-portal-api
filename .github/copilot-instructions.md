# Library Portal API - Copilot Instructions

## Project Overview

This is a FastAPI-based REST API for serving MIT Library Question Papers. The API provides organized access to question papers with filtering, search, and metadata capabilities. It includes an automated scraper that runs weekly to fetch new papers.

**Key Features:**
- FastAPI backend with Pydantic models
- API key authentication for protected endpoints
- Fuzzy search capabilities using TheFuzz
- Automated scraping with Scrapy (2024+ papers only)
- Automated categorization and data validation
- **Jules AI agents** for automated maintenance, security, and bug fixing
- Deployed on Render free tier (512MB RAM limit)

> Automation requirement: Any PR created by auto-run workflows (Jules agents, scheduled jobs, or workflow_run triggers) must include a documentation update (e.g., README or .github/copilot-instructions.md) describing the change and should reference Copilot coding agent tips at https://gh.io/copilot-coding-agent-tips.

## Project Structure

```
library-portal-api/
├── app_v2/                     # Main FastAPI application
│   ├── main.py                # Application entry point, lifespan manager, CORS
│   ├── data_loader.py         # Multi-file JSON data loader
│   ├── models.py              # Pydantic models (Paper, CurriculumContext, responses)
│   ├── routes/                # API endpoint routers
│   │   ├── papers.py          # GET /api/papers with filtering & pagination
│   │   ├── metadata.py        # GET /api/metadata, /api/statistics
│   │   └── health.py          # Health check endpoints
│   ├── services/              # Business logic
│   │   ├── indexing.py        # PaperIndex class - pre-builds Dict indexes
│   │   └── search.py          # Fuzzy search using TheFuzz
│   └── middleware/            # Authentication middleware
│       └── auth.py            # APIKeyMiddleware - validates X-API-Key
├── config/                    # Configuration and settings
│   └── config_v2.py           # Pydantic settings (LIBRARY_PORTAL_ env prefix)
├── data/classified/organized/ # Categorized paper data (JSON)
│   ├── btech/                 # BTech papers
│   │   ├── branches/          # Branch-specific (CSE.json, ECE.json, etc.)
│   │   ├── first_year/        # cs_stream.json, non_cs_stream.json
│   │   ├── common_electives.json
│   ├── masters/               # mtech.json, mca.json, me.json
│   ├── bsc/                   # icas.json
│   └── other.json             # Uncategorized papers
├── scraper/                   # Scrapy-based web scraper
│   ├── library_scraper/       # Scrapy spider, middlewares, settings
│   │   └── spiders/           # question_papers_enhanced.py
│   ├── scraper_config.py      # Year thresholds (TARGET_YEAR_THRESHOLD=2024)
│   └── scrape_log.json        # Scraping history log
├── scripts/                   # Utility scripts
│   ├── add_program_abbrev.py  # Add/update program_abbrev field
│   └── processing/            # Data processing scripts
│       ├── paper_categorizer.py    # Categorization logic with confidence scoring
│       ├── validate_data.py        # Data integrity checks
│       ├── run_categorizer.py      # Categorizer CLI runner
│       └── staging_handler.py      # Manual review queue handler
├── staging/                   # Papers pending manual review
│   └── pending_review.json    # Queue of papers needing classification
├── docs/                      # Documentation
└── .github/workflows/         # GitHub Actions workflows
    ├── scraper-v2.yml              # Weekly scraper automation (Sunday 2 AM UTC)
    ├── security-agent.yml          # Security scan (Tuesday 6 AM UTC, Jules)
    ├── jules-paper-classifier.yml  # Auto-classify pending papers (Jules)
    ├── jules-ci-failure-fixer.yml  # Auto-fix CI failures (Jules)
    ├── jules-weekly-cleanup.yml    # Weekly code cleanup (Monday 3 AM UTC, Jules)
    ├── jules-bug-fixer.yml         # Auto-fix bugs from issues (Jules)
    ├── jules-performance-agent.yml # Performance optimization (Wednesday 4 AM UTC, Jules)
    └── keep-alive.yml              # Keep Render API alive
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
- Use `create_paginated_response` helper in `app_v2/routes/papers.py` for consistent pagination logic
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
- **Target years:** 2024 and newer (configured in `scraper/scraper_config.py`)
- **Blacklisted years:** 2006-2023 (already organized, avoid re-scraping)
- Scraper runs weekly via GitHub Actions (Sunday 2 AM UTC)
- Manual trigger available via workflow_dispatch

### Categorization Logic
First-year papers (2024+) are categorized by stream:
- **CS Stream:** Course codes matching `CSS*` or `XX02` pattern
- **Core/Non-CS Stream:** Course codes matching `XX71` or `XX72` pattern

Other papers are categorized by branch/program based on course code prefixes.

## GitHub Actions Workflows

### Scraper Workflow
The main workflow for automated paper scraping:
- **Schedule:** Weekly on Sunday at 2 AM UTC
- **Workflow:** `.github/workflows/scraper-v2.yml`
- **Steps:**
  1. Pre-scrape validation (count existing papers)
  2. Run scraper (2024+ papers only)
  3. Categorize new papers
  4. Validate data integrity
  5. Commit changes (if any)
  6. Check staging queue for manual reviews

**Dry run mode:** Available via manual workflow dispatch for testing.

## Jules AI Agents

This repository uses [Jules](https://jules.google) - an AI coding agent from Google Labs - to automate various maintenance and development tasks. Jules is invoked via GitHub Actions using the [jules-action](https://github.com/google-labs-code/jules-action).

### Setup Requirements

To use Jules agents, you need to:
1. Get a Jules API key from [jules.google.com](https://jules.google.com)
2. Add the API key as a GitHub secret named `JULES_API_KEY`
   - Go to **Settings** → **Secrets and variables** → **Actions**
   - Click **New repository secret**
   - Name: `JULES_API_KEY`, Value: your key

### Available Agents

| Agent | Workflow | Trigger | Description |
|-------|----------|---------|-------------|
| **Paper Classifier** | `jules-paper-classifier.yml` | After scraper completes | Auto-classifies papers in `staging/pending_review.json` |
| **CI Failure Fixer** | `jules-ci-failure-fixer.yml` | When scraper workflow fails | Analyzes and fixes CI failures |
| **Security Scanner** | `security-agent.yml` | Tuesday at 6 AM UTC | Scans for security vulnerabilities |
| **Weekly Cleanup** | `jules-weekly-cleanup.yml` | Monday at 3 AM UTC | Removes dead code, improves quality |
| **Bug Fixer** | `jules-bug-fixer.yml` | Issue labeled with `bug` | Auto-diagnoses and fixes bugs |
| **Performance Agent** | `jules-performance-agent.yml` | Wednesday at 4 AM UTC | Finds and implements optimizations |

### Paper Classifier Agent
Automatically classifies papers from the staging queue after each scraper run:
- Reads `staging/pending_review.json` for pending papers with `reviewed: false`
- Analyzes course codes using prefix mappings (CSE→CSE, VLS→M.Tech VLSI, CSS→CS stream)
- Detects first-year streams: CS stream (CSS prefix, XX02 codes) vs Core stream (XX71, XX72 codes)
- Categorizes into correct data files under `data/classified/organized/`
- Updates staging file to mark papers as reviewed with `final_target` path
- Creates a PR with classified papers

### CI Failure Fixer Agent
Monitors the Library Portal V2 Scraper workflow and fixes failures:
- Triggers automatically when scraper workflow fails
- Analyzes error logs and stack traces from the failed run
- Identifies common failure patterns:
  - KeyError: Missing expected fields in scraped data
  - TypeError: Async/sync generator issues in middlewares
  - Configuration mismatches in scraper_config.py
- Implements targeted fixes
- Creates a PR with the fix and references the failed run

### Security Scanner Agent
Weekly security audit of the codebase (Tuesday 6 AM UTC):
- Checks for hardcoded secrets and credentials in source code
- Scans for injection vulnerabilities (command, path traversal, JSON)
- Validates authentication logic in `app_v2/middleware/auth.py`
- Reviews CORS configuration in `app_v2/main.py`
- Checks `requirements.txt` for known vulnerabilities

### Weekly Cleanup Agent
Automated code maintenance (Monday 3 AM UTC):
- Removes unused imports and dead code
- Adds missing type hints and docstrings (Google style)
- Identifies and refactors duplicated code
- Runs Black formatter: `black .`
- Validates data: `python scripts/processing/validate_data.py`
- Only creates PR if meaningful improvements found

### Bug Fixer Agent
Responds to bug reports:
- Triggered when an issue is labeled with `bug`
- **Security:** Only processes issues from trusted users (configurable allowlist in workflow)
- Analyzes bug report and traces through codebase
- Implements minimal, targeted fix following existing patterns
- Validates with: `python scripts/processing/validate_data.py`
- Tests API starts: `uvicorn app_v2.main:app`

### Performance Agent
Optimizes API performance (Wednesday 4 AM UTC):
- Analyzes data loading patterns in `app_v2/data_loader.py`
- Reviews indexing efficiency in `app_v2/services/indexing.py`
- Checks for slow fuzzy search in `app_v2/services/search.py`
- Looks for N+1 patterns and missing early returns
- Considers Render free tier constraint (512MB RAM)
- **Optimization Strategy:** The "Turbo" methodology focuses on 5 steps: Profile, Select, Optimize, Verify, and Present.
- **Tip:** When optimizing filtering logic, prefer `PaperIndex` methods that return sets of URLs (`get_urls_by_*`) over those that return full objects, to allow for efficient set intersection before object hydration.

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
    """Derive program abbreviation from paper data using 4-priority strategy with fallback."""
    
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
- **Optimization Strategy:** The "Turbo" methodology focuses on 5 steps: Profile, Select, Optimize, Verify, and Present.
- **Tip:** When optimizing filtering logic, prefer `PaperIndex` methods that return sets of URLs (`get_urls_by_*`) over those that return full objects, to allow for efficient set intersection before object hydration.

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

## Copilot Agent Tips

To get the most out of Copilot Agents (like Jules), follow these tips (ref: https://gh.io/copilot-coding-agent-tips):

1. **Be specific and provide context**: When asking for changes, reference specific files or logical components.
2. **Review and iterate**: Inspect the agent's plan and code. Provide feedback to refine the solution.
3. **Use documentation**: Keep `README.md` and `AGENTS.md` (or this file) up to date to guide the agent's understanding of the project structure and constraints.
4. **Small steps**: Break down complex tasks into smaller, verifiable steps.

## Questions?
When in doubt:
1. Check existing code patterns in similar files
2. Review FastAPI and Pydantic documentation
3. Test changes locally before committing
4. Validate data integrity after modifications
5. Consult README.md for high-level architecture
