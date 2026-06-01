# Contributing

Thanks for helping improve `library-portal-api`.

## Local Setup

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

Run the API locally:

```sh
uvicorn app_v2.main:app --reload --port 8000
```

## PR Guidelines

- Keep PRs small and focused.
- Run `pytest -q` before opening a PR.
- Update README/docs when changing API endpoints, query parameters, response schemas, deployment config, or data format.
- Validate data changes with `python scripts/processing/validate_data.py` when touching organized paper data.
- Do not commit API keys, environment files, deployment credentials, private logs, or generated secrets.
- Prefer tests with local fixtures over network-dependent scraper runs.

## API Compatibility

Avoid breaking existing consumers without documenting the migration. For new filters or response fields, keep behavior composable with existing `year`, `semester`, `course_code`, `program_abbrev`, `search`, `sort`, and `order` parameters.

## Security-sensitive Changes

Authentication, rate limits, CORS, reload endpoints, path handling, scraper scope, and logging changes need extra review.