# Architecture Overview

```mermaid
flowchart LR
    Client -->|HTTP| FastAPI
    FastAPI --> Auth[APIKeyMiddleware]
    Auth --> Headers[SecurityHeadersMiddleware]
    FastAPI --> Routes[API Routes]
    Routes --> Index[PaperIndex]
    Index --> Loader[DataLoader]
    Loader --> Data[(JSON files)]
    Routes --> Search[Search Service]
    Routes --> Health[Health Routes]
    Metrics[/metrics (optional)/] --> FastAPI
```

## Data Flow

1. Startup loads JSON files from `data/classified/organized`.
2. `DataLoader` aggregates papers and builds stats.
3. `PaperIndex` builds URL-based indexes for fast filtering.
4. `/api/papers` applies filters, search, and pagination.
