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
| `SCHOLARXIV_API_KEY` | API key for paper lookups |
| `VOXIDE_PUBLISHABLE_KEY` | Publishable key for voice service |

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

## Project Structure

```
├── docker-compose.yml          # PostgreSQL + pgvector
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # FastAPI entry point
│       ├── core/
│       │   ├── config.py       # Pydantic BaseSettings
│       │   └── database.py     # SQLAlchemy engine & session
│       ├── models/             # SQLAlchemy ORM models
│       ├── schemas/            # Pydantic request/response schemas
│       ├── routers/            # API route handlers
│       └── services/           # Business logic layer
└── docs/                       # Architecture & API documentation
```

## Architecture

The backend follows **Clean Architecture**:

- **Routers** → HTTP layer (thin, delegates to services)
- **Services** → Business logic (RAG ingestion, rubric engine)
- **Models** → Database entities (SQLAlchemy + pgvector)
- **Schemas** → Validation & serialization (Pydantic)

## License

Private — all rights reserved.
