"""Pydantic schemas for thesis endpoints."""

import uuid

from pydantic import BaseModel


class ThesisUploadResponse(BaseModel):
    id: uuid.UUID
    title: str
    ingestion_status: str

    model_config = {"from_attributes": True}


class ThesisStatusResponse(BaseModel):
    id: uuid.UUID
    ingestion_status: str

    model_config = {"from_attributes": True}
