"""Pydantic schemas for user endpoints."""

import uuid

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    institution: str | None = None
    preferred_language: str | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    institution: str | None
    preferred_language: str | None

    model_config = {"from_attributes": True}
