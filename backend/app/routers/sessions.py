"""Defense session lifecycle endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.core.database import get_db
from app.models import Question, Session
from app.schemas.sessions import (
    AnswerRequest,
    AnswerResponse,
    HintResponse,
    QuestionResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionReportResponse,
)
from app.services.session import (
    create_session,
    end_session,
    generate_hint,
    generate_question,
    generate_report,
    get_next_category,
    grade_answer,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionCreateResponse, status_code=201)
def create_new_session(
    body: SessionCreateRequest,
    db: DBSession = Depends(get_db),
):
    """Initialize a defense session linked to a thesis."""
    session, first_category = create_session(
        body.thesis_id, body.user_id, body.language, db
    )
    return SessionCreateResponse(
        id=session.id,
        thesis_id=session.thesis_id,
        status=session.status,
        current_category=first_category,
    )


@router.get("/{session_id}/next-question", response_model=QuestionResponse)
def next_question(
    session_id: uuid.UUID,
    db: DBSession = Depends(get_db),
):
    """Generate and return the next rubric-based question."""
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != "in_progress":
        raise HTTPException(status_code=400, detail="Session is not in progress")

    category = get_next_category(session, db)
    if category is None:
        raise HTTPException(
            status_code=400, detail="All rubric categories have been covered"
        )

    question = generate_question(session, category, db)
    return question


@router.post("/{session_id}/answers", response_model=AnswerResponse)
def submit_answer(
    session_id: uuid.UUID,
    body: AnswerRequest,
    db: DBSession = Depends(get_db),
):
    """Submit an answer transcript and receive grading."""
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Find the most recent unanswered question
    question = (
        db.query(Question)
        .filter(Question.session_id == session_id, Question.answer == None)  # noqa: E711
        .order_by(Question.sequence_number.desc())
        .first()
    )
    if question is None:
        raise HTTPException(
            status_code=400, detail="No unanswered question found for this session"
        )

    answer = grade_answer(question.id, body.transcript, db)
    return answer


@router.get("/{session_id}/hint", response_model=HintResponse)
def request_hint(
    session_id: uuid.UUID,
    db: DBSession = Depends(get_db),
):
    """Generate a spoken hint for the current unanswered question."""
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != "in_progress":
        raise HTTPException(status_code=400, detail="Session is not in progress")

    hint_text = generate_hint(session, db)
    return HintResponse(text=hint_text)


@router.post("/{session_id}/end", response_model=SessionReportResponse)
def end_session_endpoint(
    session_id: uuid.UUID,
    db: DBSession = Depends(get_db),
):
    """End the session early and generate the report."""
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != "in_progress":
        raise HTTPException(status_code=400, detail="Session is not in progress")

    report = end_session(session, db)
    return report


@router.get("/{session_id}/report", response_model=SessionReportResponse)
def get_report(
    session_id: uuid.UUID,
    db: DBSession = Depends(get_db),
):
    """Generate and return the session report."""
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    report = generate_report(session_id, db)
    return report
