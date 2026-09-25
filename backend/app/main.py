from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import sessions_router, theses_router, users_router

DESCRIPTION = """\
**MeRmra Exam** is a voice-first thesis defense rehearsal agent.

This API powers:
- 📄 Thesis ingestion & RAG chunking
- 🎙️ Defense session orchestration
- 📊 Rubric-based scoring & feedback
"""

app = FastAPI(
    title="MeRmra Exam API",
    version="1.0.0",
    description=DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "users", "description": "User registration."},
        {"name": "theses", "description": "Thesis upload, ingestion, and retrieval."},
        {"name": "sessions", "description": "Defense session lifecycle."},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router)
app.include_router(theses_router)
app.include_router(sessions_router)


@app.get("/health")
def health():
    return {"status": "ok"}

