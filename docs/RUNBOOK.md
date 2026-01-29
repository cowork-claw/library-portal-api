# Runbook

## Common Tasks

### Start API (local)
```bash
pip install -r requirements.txt
uvicorn app_v2.main:app --reload --port 8000
```

### Health Checks
- `GET /health` for basic status
- `GET /health/data` for data integrity (requires API key)

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
2. Run categorizer if needed:
   ```bash
   python scripts/processing/paper_categorizer.py
   ```

## Deployment (Render)

1. Ensure `LIBRARY_PORTAL_API_KEY` is set.
2. Deploy via Render dashboard (uses `render.yaml`).
3. After deploy, verify:
   - `/health` returns 200
   - `/api/metadata` returns 401 without API key

## Rollback

- Use Render dashboard to redeploy the previous successful build.
