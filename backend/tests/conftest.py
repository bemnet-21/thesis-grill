"""Shared test fixtures — in-memory SQLite with PG-specific types patched."""

import uuid
import math

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models import Base, Thesis, ThesisChunk, User

# ── Patch PG-specific types for SQLite before any table creation ──────────────

from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles


@compiles(Vector, "sqlite")
def _compile_vector_sqlite(type_, compiler, **kw):
    return "TEXT"


@compiles(ARRAY, "sqlite")
def _compile_array_sqlite(type_, compiler, **kw):
    return "TEXT"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


# ── Shared in-memory SQLite (file URI with shared cache) ─────────────────────
# Using "file::memory:?cache=shared" ensures all connections see the same DB.

engine = create_engine(
    "sqlite:///file::memory:?cache=shared&uri=true",
    connect_args={"check_same_thread": False},
    pool_size=1,
    max_overflow=0,
    poolclass=None,  # use default NullPool behavior with StaticPool
)

# Actually, the cleanest way is StaticPool which reuses a single connection:
from sqlalchemy.pool import StaticPool

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Register sqlite3 adapters so Python lists/dicts can be stored as JSON text
# (needed because PG ARRAY and JSONB are compiled as TEXT in SQLite)
import sqlite3
import json

sqlite3.register_adapter(list, lambda val: json.dumps(val))
sqlite3.register_adapter(dict, lambda val: json.dumps(val))


TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Create tables once at import
Base.metadata.create_all(bind=engine)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def db_session():
    """Yield a DB session, then wipe all data for test isolation."""
    session = TestingSessionLocal()

    def _override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    yield session
    session.close()
    app.dependency_overrides.clear()

    # Clean up all data after each test (reverse FK order)
    cleanup = TestingSessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        cleanup.execute(table.delete())
    cleanup.commit()
    cleanup.close()


@pytest.fixture()
def client():
    return TestClient(app)


# ── Factory fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def sample_user(db_session):
    user = User(
        name="Test Student",
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        institution="Test University",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def sample_thesis(db_session, sample_user):
    thesis = Thesis(
        user_id=sample_user.id,
        title="Deep Learning for Natural Language Processing",
        ingestion_status="ready",
        abstract="This thesis explores transformer architectures for NLP tasks.",
    )
    db_session.add(thesis)
    db_session.commit()
    db_session.refresh(thesis)
    return thesis


@pytest.fixture()
def thesis_with_chunks(db_session, sample_thesis):
    """Create a thesis with pre-populated chunks (embeddings stored as text in SQLite)."""
    for i in range(5):
        chunk = ThesisChunk(
            thesis_id=sample_thesis.id,
            section_label=f"page_{i}",
            text=f"This is chunk {i} about topic {['methodology', 'results', 'related work', 'contribution', 'conclusion'][i]}.",
            embedding=None,
        )
        db_session.add(chunk)
    db_session.commit()
    return sample_thesis


def make_deterministic_vector(seed: int = 0, dim: int = 1024) -> list[float]:
    """Generate a deterministic vector for testing."""
    return [math.sin(seed + i) * 0.1 for i in range(dim)]
