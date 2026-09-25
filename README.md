# MeRmra Exam

A voice-first thesis defense rehearsal agent. Upload your thesis, and MeRmra will grill you with rubric-based questions — just like a real defense committee.

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+

### 1. Start the database

```bash
docker compose up -d
```

This spins up PostgreSQL 16 with the **pgvector** extension.

### 2. Set up the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment

Copy the example env file and fill in your keys:

```bash
cp .env.example backend/.env
```

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `OPENAI_API_KEY` | OpenAI API key (embeddings + LLM) |
| `SCHOLARXIV_API_KEY` | ScholarXIV API key (`sxv_...`) for paper lookups |
| `UPLOAD_BACKEND` | `local` (default) or `s3` |
| `UPLOAD_DIR` | Local PDF storage path (default: `uploads`) |
| `S3_BUCKET` | S3 bucket name (when `UPLOAD_BACKEND=s3`) |
| `VOXIDE_PUBLISHABLE_KEY` | Publishable key for voice service (Phase 2) |

### 4. Run the API

```bash
cd backend
uvicorn app.main:app --reload
```

### 5. Explore the API docs

| URL | Interface |
|-----|-----------|
| [localhost:8000/docs](http://localhost:8000/docs) | Swagger UI (interactive) |
| [localhost:8000/redoc](http://localhost:8000/redoc) | ReDoc (reference) |
| [localhost:8000/health](http://localhost:8000/health) | Health check |

### 6. Run tests

```bash
cd backend
pytest tests/ -v
```

All tests use an in-memory SQLite DB with mocked external services — no API keys or live DB needed.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/theses` | Upload thesis PDF (multipart form) |
| `GET` | `/api/theses/{id}/status` | Check ingestion status |
| `POST` | `/api/sessions` | Start a defense session |
| `GET` | `/api/sessions/{id}/next-question` | Get next rubric question |
| `POST` | `/api/sessions/{id}/answers` | Submit answer for grading |
| `GET` | `/api/sessions/{id}/report` | Generate session report |

## Project Structure

```
├── docker-compose.yml          # PostgreSQL + pgvector
├── backend/
│   ├── requirements.txt
│   ├── tests/                  # pytest suite
│   └── app/
│       ├── main.py             # FastAPI entry point
│       ├── core/
│       │   ├── config.py       # Pydantic BaseSettings
│       │   └── database.py     # SQLAlchemy engine & session
│       ├── models/             # SQLAlchemy ORM models
│       ├── schemas/            # Pydantic request/response schemas
│       │   ├── theses.py       # Thesis upload & status schemas
│       │   └── sessions.py     # Session lifecycle schemas
│       ├── routers/            # API route handlers
│       │   ├── theses.py       # /api/theses endpoints
│       │   └── sessions.py     # /api/sessions endpoints
│       └── services/           # Business logic layer
│           ├── rag.py          # PDF ingestion & retrieval (LangChain + pgvector)
│           ├── session.py      # Rubric engine, grading, reports
│           ├── scholarxiv.py   # ScholarXIV Papers API client
│           └── storage.py      # PDF storage (local / S3)
└── docs/                       # Architecture & API documentation
```

## Architecture

The backend follows **Clean Architecture**:

- **Routers** → HTTP layer (thin, delegates to services)
- **Services** → Business logic (RAG ingestion, rubric engine, ScholarXIV client)
- **Models** → Database entities (SQLAlchemy + pgvector)
- **Schemas** → Validation & serialization (Pydantic)

## License

Private — all rights reserved.
