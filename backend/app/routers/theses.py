"""Thesis upload and ingestion endpoints."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Thesis, User
from app.schemas.theses import ThesisStatusResponse, ThesisUploadResponse
from app.services.rag import ingest_thesis
from app.services.storage import save_pdf

router = APIRouter(prefix="/api/theses", tags=["theses"])


@router.post("", response_model=ThesisUploadResponse, status_code=201)
def upload_thesis(
    file: UploadFile,
    title: str = Form(...),
    user_id: uuid.UUID = Form(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """Upload a thesis PDF, create a record, and dispatch ingestion."""
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    content = file.file.read()
    filename = f"{uuid.uuid4()}_{file.filename}"
    pdf_path = save_pdf(filename, content)

    thesis = Thesis(
        user_id=user_id,
        title=title,
        uploaded_pdf_url=pdf_path,
        ingestion_status="pending",
    )
    db.add(thesis)
    db.commit()
    db.refresh(thesis)

    background_tasks.add_task(ingest_thesis, thesis.id, pdf_path, db)
    return thesis


@router.get("/{thesis_id}/status", response_model=ThesisStatusResponse)
def get_thesis_status(
    thesis_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Return the current ingestion status of a thesis."""
    thesis = db.get(Thesis, thesis_id)
    if thesis is None:
        raise HTTPException(status_code=404, detail="Thesis not found")
    return thesis
