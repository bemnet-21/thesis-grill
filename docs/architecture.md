# Backend Architecture

## Overview

MeRmra Exam uses a **Clean Architecture** pattern to keep concerns separated and the codebase maintainable as features grow.

```
Request → Router → Service → Model/DB
                 ↘ Schema (validation)
```

## Layers

### Routers (`app/routers/`)

Thin HTTP handlers. Each router:
- Declares endpoints and HTTP methods
- Validates input via Pydantic schemas (dependency injection)
- Delegates all logic to the service layer
- Returns Pydantic response schemas

| File | Prefix | Responsibility |
|------|--------|----------------|
| `theses.py` | `/theses` | Thesis CRUD, PDF upload, ingestion triggers |
| `sessions.py` | `/sessions` | Session lifecycle, question flow, reports |

### Services (`app/services/`)

Core business logic. Services are plain Python classes/functions — no HTTP or framework awareness.

Planned services:
- **Ingestion** — PDF parsing → chunking → embedding via pgvector
- **Rubric Engine** — Question generation from rubric categories
- **Scoring** — Answer evaluation with rubric feedback
- **Report Generator** — Per-category breakdown and overall scoring

### Models (`app/models/`)

SQLAlchemy ORM models mapping to PostgreSQL tables. Key design decisions:

- **UUIDs** as primary keys (no auto-increment leakage)
- **pgvector `Vector(1536)`** on `ThesisChunk.embedding` for similarity search
- **PostgreSQL enums** for constrained fields (`ingestion_status`, `session_status`, `session_language`)
- **JSONB** for flexible structured data (`rubric_feedback`, `per_category_breakdown`)

### Schemas (`app/schemas/`)

Pydantic models for request/response validation. Separate from ORM models to decouple API shape from database shape.

### Core (`app/core/`)

Cross-cutting infrastructure:

| File | Purpose |
|------|---------|
| `config.py` | `BaseSettings` — loads env vars from `.env` |
| `database.py` | SQLAlchemy engine, `SessionLocal`, `get_db` dependency |

## Data Model

```
User ──┬── Thesis ──┬── ThesisChunk (with embedding)
       │            └── Session ──┬── Question ── Answer
       └── Session                └── SessionReport
```

### Entity Summary

| Entity | Key Fields | Notes |
|--------|-----------|-------|
| **User** | email (unique), institution, preferred_language | |
| **Thesis** | title, ingestion_status, abstract | Status enum: pending → chunked → embedded → ready / failed |
| **ThesisChunk** | section_label, text, embedding | `Vector(1536)` — dimension matches OpenAI ada-002 |
| **Session** | language (am/en), status, timestamps | One session = one mock defense |
| **Question** | rubric_category, sequence_number | related_paper_ids for citation-backed questions |
| **Answer** | transcript, score, rubric_feedback | triggered_pushback flags follow-up probes |
| **SessionReport** | overall_score, per_category_breakdown | Generated after session completion |

## API Documentation

FastAPI auto-generates interactive API docs:

| Endpoint | Format |
|----------|--------|
| `/docs` | Swagger UI — interactive, try-it-out |
| `/redoc` | ReDoc — clean reference documentation |
| `/openapi.json` | Raw OpenAPI 3.1 spec |
