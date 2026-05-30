# Runbook

## Common Tasks

### Start API (local)
```bash
pip install -r requirements.txt
uvicorn app_v2.main:app --reload --port 8000
```

### Health Checks
- `GET /health` for basic status (public — no API key)
- `GET /health/data` for data integrity (requires API key)
- `GET /health/scraper` for scraper run history and config status (requires API key)

> `/health` is the only public health endpoint. `/health/data`, `/health/scraper`,
> `/metrics`, and all `/api/*` routes require the `X-API-Key` header.

### Reload data without restart (admin)
Reload the organized JSON into a freshly built index and atomically swap it in, with no
service restart:
```bash
curl -X POST -H "X-API-Key: your-key" http://localhost:8000/health/data/reload
```
Returns `202 Accepted` with `{"reload_id": "...", "message": "Reload started"}`. The
reload runs in the background; check `/health/data` afterward to confirm the new paper
count.

### Metrics (optional)
Set `LIBRARY_PORTAL_METRICS_ENABLED=true`, then:
- `GET /metrics` (requires API key)

### Error Tracking (optional)
Set `LIBRARY_PORTAL_SENTRY_DSN` and restart the API.

## Data Issues

### Data not loading
1. Confirm `LIBRARY_PORTAL_DATA_DIRECTORY` (default is `data/classified/organized`).
2. Check logs for JSON errors.
3. Run validation:
   ```bash
   python scripts/processing/validate_data.py
   ```

### Missing papers
1. Check `staging/pending_review.json`.
2. Run the categorizer if needed. The runnable entry point is `run_categorizer.py`
   (`paper_categorizer.py` is an importable library module with no CLI). It takes the
   scraped papers JSON as a required positional argument:
   ```bash
   python scripts/processing/run_categorizer.py scraper/scraped_output.json
   ```
   Add `--dry-run` to preview categorization without writing any files.

## Deployment (Render)

1. Ensure `LIBRARY_PORTAL_API_KEY` is set.
2. Deploy via Render dashboard (uses `render.yaml`).
3. After deploy, verify:
   - `/health` returns 200
   - `/api/metadata` returns 401 without API key

## Rollback

- Use Render dashboard to redeploy the previous successful build.
