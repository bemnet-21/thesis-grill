import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ── User ─────────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    institution: Mapped[str | None] = mapped_column(String(255))
    preferred_language: Mapped[str | None] = mapped_column(String(10))

    theses: Mapped[list["Thesis"]] = relationship(back_populates="user")
    sessions: Mapped[list["Session"]] = relationship(back_populates="user")


# ── Thesis ────────────────────────────────────────────────────────────────────


INGESTION_STATUS = Enum(
    "pending",
    "chunked",
    "embedded",
    "ready",
    "failed",
    name="ingestion_status",
)


class Thesis(Base):
    __tablename__ = "theses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_pdf_url: Mapped[str | None] = mapped_column(Text)
    ingestion_status: Mapped[str] = mapped_column(
        INGESTION_STATUS, server_default="pending", nullable=False
    )
    abstract: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="theses")
    chunks: Mapped[list["ThesisChunk"]] = relationship(back_populates="thesis")
    sessions: Mapped[list["Session"]] = relationship(back_populates="thesis")


# ── ThesisChunk ───────────────────────────────────────────────────────────────


class ThesisChunk(Base):
    __tablename__ = "thesis_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    thesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("theses.id"), nullable=False
    )
    section_label: Mapped[str | None] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1536))  # OpenAI ada-002 dimension

    thesis: Mapped["Thesis"] = relationship(back_populates="chunks")


# ── Session ───────────────────────────────────────────────────────────────────


SESSION_LANGUAGE = Enum("am", "en", name="session_language")
SESSION_STATUS = Enum(
    "in_progress", "completed", "abandoned", name="session_status"
)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    thesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("theses.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    language: Mapped[str] = mapped_column(SESSION_LANGUAGE, nullable=False)
    status: Mapped[str] = mapped_column(
        SESSION_STATUS, server_default="in_progress", nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    thesis: Mapped["Thesis"] = relationship(back_populates="sessions")
    user: Mapped["User"] = relationship(back_populates="sessions")
    questions: Mapped[list["Question"]] = relationship(back_populates="session")
    report: Mapped["SessionReport | None"] = relationship(
        back_populates="session", uselist=False
    )


# ── Question ──────────────────────────────────────────────────────────────────


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False
    )
    rubric_category: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    related_paper_ids = mapped_column(ARRAY(String), nullable=True)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)

    session: Mapped["Session"] = relationship(back_populates="questions")
    answer: Mapped["Answer | None"] = relationship(
        back_populates="question", uselist=False
    )


# ── Answer ────────────────────────────────────────────────────────────────────


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False
    )
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    rubric_feedback = mapped_column(JSONB, nullable=True)
    triggered_pushback: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    question: Mapped["Question"] = relationship(back_populates="answer")


# ── SessionReport ─────────────────────────────────────────────────────────────


class SessionReport(Base):
    __tablename__ = "session_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id"), unique=True, nullable=False
    )
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    per_category_breakdown = mapped_column(JSONB, nullable=True)
    strengths: Mapped[str | None] = mapped_column(Text)
    weaknesses: Mapped[str | None] = mapped_column(Text)

    session: Mapped["Session"] = relationship(back_populates="report")
