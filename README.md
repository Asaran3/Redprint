# Redprint

Submit a property address and a blueprint PDF, get back a building-code compliance report.

Redprint is not a code-lookup chatbot. There is no question box. You upload a plan
set and a location, and it reviews the whole drawing the way a plans examiner
would — zoning, height, occupancy, egress, fire, accessibility, parking, energy,
structural, plumbing, and life safety — citing the municipal code for that
jurisdiction.

## How it works

```
address + blueprint.pdf
        │
        ├─ geocode ────────► city, county, state (OpenStreetMap / Nominatim)
        │
        ├─ read the plans ─► sheet text + page images (AI vision)
        │
        ├─ retrieve code ──► city-scoped pgvector search across review topics
        │
        └─ evaluate ───────► Claude writes findings grounded in retrieved code
                             │
                             └─► structured JSON report
```

### AI-driven PDF parsing

Parsing is the hard part of this problem, and it is AI-driven on both sides of
the pipeline. PyMuPDF only supplies raw layout; the interpretation is done by
models.

**Submitted blueprints** (`backend/services/blueprint.py`) are not treated as
text documents. Plan sets carry most of their meaning in geometry, dimension
strings, and title blocks that extract as unordered fragments or as nothing at
all. So each sheet is rendered to an image and sent to **Claude as vision
input**, alongside whatever text layer exists. The model reads the drawing.

**Municipal code documents** (`backend/enterprise_parser.py`) go through a
three-stage AI parse during ingestion:

1. **LLM structure mapping** — `gpt-4o-mini` reads the front matter and table of
   contents and returns a JSON map of the document's sections, so chunks can be
   bound to the right code section.
2. **Noise filtering** — deterministic rules drop page numbers, running headers,
   and boilerplate before anything is embedded.
3. **Semantic boundary chunking** — every layout block is embedded, and adjacent
   blocks are compared by cosine similarity. A new chunk starts when the topic
   actually shifts (similarity below `0.72`) rather than at a fixed token count,
   so a regulation is not split down the middle.

### Grounding

The report is constrained to retrieved code. If a topic is visible on the plans
but no matching code was retrieved, or the drawing lacks the detail to judge it,
the finding is `INSUFFICIENT_EVIDENCE` — not a guessed pass or fail. A
`NONCOMPLIANT` finding requires an actual conflict with a cited chunk.

## API

`POST /api/analyze` — multipart form: `address` (string), `blueprint` (PDF, 25 MB max)

```json
{
  "filename": "plans.pdf",
  "jurisdiction": { "city": "San Francisco", "county": "", "state": "California" },
  "overall_status": "MIXED",
  "executive_summary": "...",
  "findings": [
    {
      "category": "Egress",
      "status": "NONCOMPLIANT",
      "title": "Exit corridor width below minimum",
      "observation": "What the drawing shows",
      "code_citation": "Section 1005.3",
      "code_excerpt": "Quoted from retrieved code only",
      "recommendation": "What to change",
      "sheet_hint": "Sheet A-2"
    }
  ],
  "coverage": {
    "pages_reviewed": 8,
    "code_chunks_used": 18,
    "jurisdiction_filter": "San Francisco",
    "notes": "What could not be checked"
  }
}
```

`overall_status` is `PASS`, `FAIL`, `MIXED`, or `INSUFFICIENT_EVIDENCE`. Each
finding is `COMPLIANT`, `NONCOMPLIANT`, `INSUFFICIENT_EVIDENCE`, or
`NOT_APPLICABLE`.

Check `coverage.jurisdiction_filter`. If it reads `unfiltered-fallback`, no code
was tagged for that city and retrieval fell back to the whole library — citations
may come from the wrong jurisdiction.

## Stack

| Layer | Choice |
|---|---|
| API | FastAPI, Pydantic |
| Database | Supabase Postgres + pgvector |
| Embeddings | OpenAI `text-embedding-3-small` (1536-dim) |
| Reasoning / vision | Anthropic Claude |
| Structure mapping | OpenAI `gpt-4o-mini` |
| PDF layout | PyMuPDF |
| Geocoding | OpenStreetMap Nominatim |
| Frontend | Next.js 16, React 19, Tailwind CSS 4 |

## Setup

Requires Python 3.14, Node 20+, and a Supabase project with `pgvector` enabled.

```bash
# Backend
cd backend
python3 -m venv venv
./venv/bin/pip install fastapi uvicorn python-multipart pydantic-settings \
  python-dotenv sqlalchemy psycopg2-binary pymupdf openai anthropic requests numpy

cp .env.example .env   # fill in DATABASE_URL, OPENAI_API_KEY, ANTHROPIC_API_KEY
./venv/bin/uvicorn main:app --reload
```

```bash
# Frontend, in a second terminal
cd frontend
npm install
npm run dev
```

The UI runs at `http://localhost:3000` and expects the API at
`http://localhost:8000`. Override with `NEXT_PUBLIC_API_URL`.

Restart uvicorn after editing `.env` — `--reload` watches Python files, not
environment variables.

### Code library

The knowledge base is one table:

```sql
municipal_codes (id, city_name, code_section, chunk_text, embedding vector(1536))
```

Retrieval filters on `city_name`, so each jurisdiction must be ingested before
its plans can be reviewed:

```bash
cd backend
./venv/bin/python run_ingest.py   # edit the PDF path and city name inside
```

## Status

Working end to end: geocoding, AI blueprint parsing, AI code parsing and
ingestion, city-scoped retrieval, report generation, and the upload UI.

Currently ingested: **San Francisco** only. Any other jurisdiction will return
mostly `INSUFFICIENT_EVIDENCE` until its codes are loaded.

Not built yet: space-optimization suggestions, 2D→3D model generation, S3 upload,
containerization, and deployment.
