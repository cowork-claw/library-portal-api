# Library Portal API - Frontend Integration Guide

## API Base URL

```
https://library-portal-api.onrender.com
```

---

## Authentication

All `/api/*` endpoints and `/health/data` require an API key in the `X-API-Key` header.

### Method

| Method | Example |
|--------|---------|
| **Header** | `X-API-Key: your-key` |

### JavaScript Example

```javascript
const API_BASE = 'https://library-portal-api.onrender.com';
const API_KEY = 'your-api-key-here';

async function fetchPapers(filters = {}) {
  const params = new URLSearchParams(filters);
  
  const response = await fetch(`${API_BASE}/api/papers?${params}`, {
    headers: {
      'X-API-Key': API_KEY,
      'Content-Type': 'application/json'
    }
  });
  
  return response.json();
}
```

### Public Endpoints (no auth required)

- `GET /` - API info
- `GET /docs` - Swagger UI
- `GET /redoc` - ReDoc
- `GET /openapi.json` - OpenAPI schema
- `GET /health` - Health check

### Operational Endpoints (API key required)

- `GET /health/data` - Data health
- `GET /health/scraper` - Scraper health (last run, totals)
- `POST /health/data/reload` - Admin hot reload of data (returns `202 Accepted`)

> Note: `/health` is the only public health endpoint. `/health/data`, `/health/scraper`, and `/health/data/reload` all require the `X-API-Key` header.

---

## Endpoints

### Papers

#### List Papers with Filters
```
GET /api/papers
```

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `year` | int | Filter by year (2000-2100) |
| `semester` | int | Filter by semester (1-8) |
| `program` | string | Filter by program name (max 50 chars) |
| `degree_type` | string | Filter by degree type (max 50 chars), e.g. B.Tech, M.Tech |
| `paper_type` | string | Filter by paper type (max 50 chars), e.g. Regular, Makeup |
| `course_code` | string | Filter by full course code (max 20 chars), e.g. CSE2101 |
| `stream` | string | Filter by stream (max 20 chars), e.g. cs, core |
| `program_abbrev` | string | Filter by program abbreviation (1-20 chars, case-insensitive), e.g. CSE, ECE |
| `search` | string | Fuzzy search (2-100 chars) |
| `sort` | string | Sort field: `year`, `semester`, or `relevance` |
| `order` | string | Sort order: `asc` or `desc` (default: `desc`) |
| `limit` | int | Number of results to return (default: 50, max: 500) |
| `offset` | int | Number of results to skip for pagination (default: 0, min: 0) |

**Example:**
```javascript
// Get CSE program papers from 2024, second page of 50
fetch(`${API_BASE}/api/papers?year=2024&program_abbrev=CSE&limit=50&offset=50`, {
  headers: { 'X-API-Key': API_KEY }
})
```

**Response:**
```json
{
  "papers": [
    {
      "file_name": "CSE2101_Data_Structures.pdf",
      "url": "https://...",
      "course_code": "CSE2101",
      "course_name": "Data Structures",
      "year": 2024,
      "semester": 3,
      "program": "B.Tech Computer Science and Engineering",
      "program_abbrev": "CSE",
      "degree_type": "B.Tech",
      "paper_type": "Regular"
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 50,
  "pagination": {
    "total": 150,
    "limit": 50,
    "offset": 50,
    "page": 2,
    "total_pages": 3,
    "has_next": true,
    "has_prev": true
  },
  "execution_time_ms": 1.84
}
```

#### Look Up a Single Paper by URL
```
GET /api/papers/lookup?url=<exact PDF url>
```

Returns a single `Paper` object. Responds `404 {"detail": "Paper not found"}` if no paper matches the exact URL.

```javascript
const url = 'https://libportal.manipal.edu/.../CSE2101.pdf';
fetch(`${API_BASE}/api/papers/lookup?url=${encodeURIComponent(url)}`, {
  headers: { 'X-API-Key': API_KEY }
})
```

#### Papers by Year
```
GET /api/papers/year/{year}
```
Optional query params: `semester` (1-8), `limit` (default 100, max 500), `offset` (min 0). Returns a `PapersResponse`.

#### Papers by Course
```
GET /api/papers/course/{course_code}
```
Returns a `CourseResponse`: `{ course_code, course_name, papers, total_papers }`.

#### Papers by Semester
```
GET /api/papers/semester/{semester}
```
Optional query params: `year` (2000-2100), `limit` (default 100, max 500), `offset` (min 0). Returns a `PapersResponse`.

---

### Metadata

#### Get Available Filter Values
```
GET /api/metadata
```

**Response:**
```json
{
  "years": [2025, 2024, 2023, 2022],
  "programs": ["B.Tech Computer Science and Engineering", "M.Tech", "..."],
  "program_abbrevs": ["CSE", "ECE", "..."],
  "semesters": [1, 2, 3, 4, 5, 6, 7, 8],
  "paper_types": ["Regular", "Makeup", "Supplementary"],
  "degree_types": ["B.Tech", "M.Tech", "MCA", "B.Sc"],
  "course_codes": ["CSE2101", "ECE3102", "..."],
  "streams": ["cs", "core"],
  "total_papers": 777
}
```

#### Get Statistics
```
GET /api/statistics
```

**Response:**
```json
{
  "total_papers": 777,
  "papers_by_year": {
    "2024": 250,
    "2023": 300
  },
  "papers_by_program": {
    "B.Tech Computer Science and Engineering": 400,
    "M.Tech": 100
  },
  "papers_by_program_abbrev": {
    "CSE": 400,
    "ECE": 150
  },
  "papers_by_semester": {
    "1": 80,
    "2": 75
  },
  "courses_count": 343,
  "files_loaded": 23
}
```

---

## Health & Operations

#### Health Check (public)
```
GET /health
```
No API key required. Returns overall status, version, uptime, and per-component health.

#### Data Health (API key required)
```
GET /health/data
```
Returns `{ status, total_papers, unique_urls, files_loaded, courses_count, last_loaded, errors, papers_by_year, papers_by_program }`.

#### Scraper Health (API key required)
```
GET /health/scraper
```
Returns `{ status, last_run, total_runs, total_scraped, total_skipped, target_year_threshold, blacklisted_years_count }`.

#### Reload Data (API key required)
```
POST /health/data/reload
```
Admin endpoint that schedules a background reload, building a new index and atomically swapping it without restarting the service. Responds `202 Accepted`:

```json
{
  "reload_id": "a1b2c3d4-...",
  "message": "Reload started"
}
```

---

## CORS Configuration

The API allows CORS from configured origins. 

**Current setting:** All origins allowed for development.

For production, update the Render environment:
```
LIBRARY_PORTAL_CORS_ORIGINS=https://your-frontend.com
```

---

## Error Responses

### 401 Unauthorized
```json
{
  "detail": "API key required",
  "hint": "Provide API key via 'X-API-Key' header"
}
```

### 403 Forbidden
```json
{
  "detail": "Invalid API key"
}
```

### 404 Not Found
```json
{
  "detail": "Paper not found"
}
```

### 429 Too Many Requests
A fixed-window rate limiter (100 requests/min per client) applies to `/api/*` and `/health/data`. When exceeded, the response includes a `Retry-After` header indicating how many seconds to wait.

```json
{
  "detail": "Rate limit exceeded"
}
```

---

## Frontend Code Examples

### React Hook
```javascript
import { useState, useEffect } from 'react';

const API_BASE = 'https://library-portal-api.onrender.com';
const API_KEY = process.env.REACT_APP_API_KEY;

export function usePapers(filters, { limit = 50, offset = 0 } = {}) {
  const [papers, setPapers] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const params = new URLSearchParams({ ...filters, limit, offset });

    fetch(`${API_BASE}/api/papers?${params}`, {
      headers: { 'X-API-Key': API_KEY }
    })
      .then(res => res.json())
      .then(data => {
        setPapers(data.papers);
        setPagination(data.pagination);
        setLoading(false);
      })
      .catch(err => {
        setError(err);
        setLoading(false);
      });
  }, [filters, limit, offset]);

  return { papers, pagination, loading, error };
}
```

> **Tip:** Memoize `filters` before passing it in (e.g. with `useMemo`). A new
> object literal on every render changes the `useEffect` dependency each time and
> triggers an infinite re-fetch loop:
>
> ```javascript
> const filters = useMemo(() => ({ year: 2024, program_abbrev: 'CSE' }), []);
> const { papers, pagination } = usePapers(filters, { limit: 50, offset: 0 });
> ```

### Fetch Wrapper
```javascript
class LibraryAPI {
  constructor(apiKey) {
    this.baseUrl = 'https://library-portal-api.onrender.com';
    this.apiKey = apiKey;
  }

  async request(endpoint, options = {}) {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        'X-API-Key': this.apiKey,
        'Content-Type': 'application/json',
        ...options.headers
      }
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }

    return response.json();
  }

  getPapers(filters = {}) {
    const params = new URLSearchParams(filters);
    return this.request(`/api/papers?${params}`);
  }

  getMetadata() {
    return this.request('/api/metadata');
  }

  getStatistics() {
    return this.request('/api/statistics');
  }

  searchPapers(query) {
    return this.request(`/api/papers?search=${encodeURIComponent(query)}`);
  }

  lookupPaper(url) {
    return this.request(`/api/papers/lookup?url=${encodeURIComponent(url)}`);
  }
}

// Usage
const api = new LibraryAPI('your-api-key');
const result = await api.getPapers({ year: 2024, semester: 3, limit: 50, offset: 0 });
console.log(result.papers, result.pagination);
```

---

## Data Structure

Each paper object contains:

```typescript
// Only `file_name` is guaranteed; the model allows extra fields, so treat
// the rest as optional. Most papers include the fields below.
interface Paper {
  file_name: string;        // PDF filename (required)
  url?: string;             // Direct PDF download URL
  path?: string;
  display_title?: string;
  course_code?: string;     // e.g., "CSE2101"
  course_name?: string;     // e.g., "Data Structures"
  year?: number;
  semester?: number;        // 1-8
  session?: string;         // "Even (May/Jun)" or "Odd (Nov/Dec)"
  program?: string;         // e.g., "B.Tech Computer Science and Engineering"
  program_abbrev?: string;  // e.g., "CSE", "ECE"
  program_name?: string;
  degree_type?: string;     // B.Tech, M.Tech, MCA, B.Sc
  paper_type?: string;      // "Regular", "Supplementary", "Makeup"
  subject_code?: string;
  subject_name?: string;
  streams?: string[];
  scraped_at?: string;      // ISO timestamp
}
```

---

## Quick Test

```bash
# Health check (no auth)
curl https://library-portal-api.onrender.com/health

# Get papers (with auth)
curl -H "X-API-Key: YOUR_KEY" https://library-portal-api.onrender.com/api/papers?year=2024

# Get metadata (with auth)
curl -H "X-API-Key: YOUR_KEY" https://library-portal-api.onrender.com/api/metadata
```

---

## Environment Variables for Frontend

```env
# .env.local
VITE_API_BASE_URL=https://library-portal-api.onrender.com
VITE_API_KEY=your-api-key-here
```

**⚠️ Security Note:** Never expose your API key in client-side code for production. Consider:
1. Using a backend proxy
2. Implementing user authentication
3. Rate limiting on the API
