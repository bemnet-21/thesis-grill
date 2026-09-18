from fastapi import FastAPI

from app.routers import sessions_router, theses_router

DESCRIPTION = """\
**MeRmra Exam** is a voice-first thesis defense rehearsal agent.

This API powers:
- 📄 Thesis ingestion & RAG chunking
- 🎙️ Defense session orchestration
- 📊 Rubric-based scoring & feedback
"""

app = FastAPI(
    title="MeRmra Exam API",
    version="0.1.0",
    description=DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "theses", "description": "Thesis upload, ingestion, and retrieval."},
        {"name": "sessions", "description": "Defense session lifecycle."},
    ],
)

app.include_router(theses_router)
app.include_router(sessions_router)


@app.get("/health")
def health():
    return {"status": "ok"}
