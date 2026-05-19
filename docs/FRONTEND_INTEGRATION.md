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
- `GET /health` - Health check

### Operational Endpoint (API key required)

- `GET /health/data` - Data health

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
| `year` | int | Filter by year (2022-2025) |
| `semester` | int | Filter by semester (1-8) |
| `course_code` | string | Filter by course code |
| `program` | string | Filter by program name |
| `degree_type` | string | Filter by degree (B.Tech, M.Tech, etc) |
| `search` | string | Fuzzy search |
| `page` | int | Page number (default: 1) |
| `page_size` | int | Items per page (default: 20, max: 100) |

**Example:**
```javascript
// Get B.Tech CSE papers from 2024
fetch(`${API_BASE}/api/papers?year=2024&degree_type=B.Tech&course_code=CSE`, {
  headers: { 'X-API-Key': API_KEY }
})
```

**Response:**
```json
{
  "papers": [
    {
      "url": "https://...",
      "file_name": "CSE2101_Data_Structures.pdf",
      "course_code": "CSE2101",
      "course_name": "Data Structures",
      "year": 2024,
      "semester": 3,
      "program": "B.Tech",
      "degree_type": "B.Tech",
      "paper_type": "End Semester"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "total_pages": 8
}
```

#### Papers by Year
```
GET /api/papers/year/{year}
```

#### Papers by Course
```
GET /api/papers/course/{course_code}
```

#### Papers by Semester
```
GET /api/papers/semester/{semester}
```

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
  "semesters": [1, 2, 3, 4, 5, 6, 7, 8],
  "degree_types": ["B.Tech", "M.Tech", "MCA", "B.Sc"],
  "course_codes": ["CSE2101", "ECE3102", ...],
  "programs": ["B.Tech", "M.Tech", ...]
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
  "total_courses": 343,
  "papers_by_year": {
    "2024": 250,
    "2023": 300,
    ...
  },
  "papers_by_degree": {
    "B.Tech": 600,
    "M.Tech": 100,
    ...
  }
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

---

## Frontend Code Examples

### React Hook
```javascript
import { useState, useEffect } from 'react';

const API_BASE = 'https://library-portal-api.onrender.com';
const API_KEY = process.env.REACT_APP_API_KEY;

export function usePapers(filters) {
  const [papers, setPapers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const params = new URLSearchParams(filters);
    
    fetch(`${API_BASE}/api/papers?${params}`, {
      headers: { 'X-API-Key': API_KEY }
    })
      .then(res => res.json())
      .then(data => {
        setPapers(data.papers);
        setLoading(false);
      })
      .catch(err => {
        setError(err);
        setLoading(false);
      });
  }, [filters]);

  return { papers, loading, error };
}
```

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
}

// Usage
const api = new LibraryAPI('your-api-key');
const papers = await api.getPapers({ year: 2024, semester: 3 });
```

---

## Data Structure

Each paper object contains:

```typescript
interface Paper {
  url: string;              // Direct PDF download URL
  file_name: string;        // PDF filename
  course_code: string;      // e.g., "CSE2101"
  course_name: string;      // e.g., "Data Structures"
  year: number;             // 2022-2025
  semester: number;         // 1-8
  program: string;          // e.g., "B.Tech"
  degree_type: string;      // B.Tech, M.Tech, MCA, B.Sc
  paper_type: string;       // "End Semester", "Mid Semester", etc.
  subject_code?: string;
  subject_name?: string;
  display_title?: string;
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
