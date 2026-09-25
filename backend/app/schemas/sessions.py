"""Pydantic schemas for session endpoints."""

import uuid
from typing import Any, Literal

from pydantic import BaseModel


class SessionCreateRequest(BaseModel):
    thesis_id: uuid.UUID
    user_id: uuid.UUID
    language: Literal["am", "en"]


class SessionCreateResponse(BaseModel):
    id: uuid.UUID
    thesis_id: uuid.UUID
    status: str
    current_category: str

    model_config = {"from_attributes": True}


class QuestionResponse(BaseModel):
    id: uuid.UUID
    rubric_category: str
    text: str
    sequence_number: int
    related_paper_ids: list[str] | None = None

    model_config = {"from_attributes": True}


class AnswerRequest(BaseModel):
    transcript: str


class AnswerResponse(BaseModel):
    id: uuid.UUID
    score: int
    rubric_feedback: dict[str, Any] | None = None
    triggered_pushback: bool

    model_config = {"from_attributes": True}


class SessionReportResponse(BaseModel):
    overall_score: int
    per_category_breakdown: dict[str, Any] | None = None
    strengths: str | None = None
    weaknesses: str | None = None

    model_config = {"from_attributes": True}
