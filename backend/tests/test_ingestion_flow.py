"""Tests for thesis upload, ingestion pipeline, and retrieval."""

import io
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models import Thesis, ThesisChunk
from app.services.rag import ingest_thesis
from tests.conftest import make_deterministic_vector


class TestThesisUpload:
    """POST /api/theses — upload and trigger ingestion."""

    def test_upload_thesis_returns_201(self, client, sample_user):
        pdf_content = b"%PDF-1.4 fake pdf content for testing"
        response = client.post(
            "/api/theses",
            data={"title": "Test Thesis", "user_id": str(sample_user.id)},
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["title"] == "Test Thesis"
        assert body["ingestion_status"] == "pending"
        assert "id" in body

    @patch("app.routers.theses.ingest_thesis")
    def test_upload_creates_db_record(self, mock_ingest, client, db_session, sample_user):
        pdf_content = b"%PDF-1.4 fake pdf content"
        response = client.post(
            "/api/theses",
            data={"title": "DB Record Thesis", "user_id": str(sample_user.id)},
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
        )
        thesis_id = response.json()["id"]
        thesis = db_session.get(Thesis, uuid.UUID(thesis_id))
        assert thesis is not None
        assert thesis.title == "DB Record Thesis"
        assert thesis.ingestion_status == "pending"
        mock_ingest.assert_called_once()


class TestThesisStatus:
    """GET /api/theses/{id}/status — ingestion status check."""

    def test_get_status(self, client, sample_thesis):
        response = client.get(f"/api/theses/{sample_thesis.id}/status")
        assert response.status_code == 200
        assert response.json()["ingestion_status"] == "ready"

    def test_get_status_not_found(self, client):
        fake_id = uuid.uuid4()
        response = client.get(f"/api/theses/{fake_id}/status")
        assert response.status_code == 404


class TestIngestionWorker:
    """Background worker: PDF → chunks → embeddings → ready."""

    @patch("app.services.rag._get_embeddings")
    @patch("app.services.rag.PyPDFLoader")
    def test_ingestion_completes_to_ready(
        self, mock_loader_cls, mock_get_embeddings, db_session, sample_user
    ):
        # Create a pending thesis
        thesis = Thesis(
            user_id=sample_user.id,
            title="Ingestion Test",
            ingestion_status="pending",
        )
        db_session.add(thesis)
        db_session.commit()
        db_session.refresh(thesis)

        # Mock PDF loading to return fake pages
        from langchain_core.documents import Document

        mock_loader = MagicMock()
        mock_loader.load.return_value = [
            Document(page_content="Chapter 1: Introduction to deep learning." * 20, metadata={"page": 0}),
            Document(page_content="Chapter 2: Methodology and experimental setup." * 20, metadata={"page": 1}),
        ]
        mock_loader_cls.return_value = mock_loader

        # Mock embeddings
        mock_embeddings = MagicMock()
        mock_embeddings.embed_documents.return_value = [
            make_deterministic_vector(i) for i in range(10)  # enough for any split
        ]
        mock_get_embeddings.return_value = mock_embeddings

        # Run ingestion
        ingest_thesis(thesis.id, "/fake/path.pdf", db_session)

        # Verify
        db_session.refresh(thesis)
        assert thesis.ingestion_status == "ready"
        chunks = db_session.query(ThesisChunk).filter_by(thesis_id=thesis.id).all()
        assert len(chunks) > 0

    @patch("app.services.rag._get_embeddings")
    @patch("app.services.rag.PyPDFLoader")
    def test_ingestion_fails_gracefully(
        self, mock_loader_cls, mock_get_embeddings, db_session, sample_user
    ):
        thesis = Thesis(
            user_id=sample_user.id,
            title="Failing Thesis",
            ingestion_status="pending",
        )
        db_session.add(thesis)
        db_session.commit()
        db_session.refresh(thesis)

        # Make the loader throw
        mock_loader = MagicMock()
        mock_loader.load.side_effect = RuntimeError("PDF parsing failed")
        mock_loader_cls.return_value = mock_loader

        ingest_thesis(thesis.id, "/fake/broken.pdf", db_session)

        db_session.refresh(thesis)
        assert thesis.ingestion_status == "failed"


class TestRetrieve:
    """Internal retrieve() — cosine similarity against pgvector."""

    @patch("app.services.rag._get_embeddings")
    def test_retrieve_returns_chunks(self, mock_get_embeddings, db_session, thesis_with_chunks):
        """Since SQLite can't do vector ops, we mock the DB execute call
        to verify the embedding + query wiring."""
        # Extract the ID before we mock session.execute
        thesis_id = thesis_with_chunks.id

        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = make_deterministic_vector(0)
        mock_get_embeddings.return_value = mock_embeddings

        from app.services import rag

        with patch.object(db_session, "execute") as mock_execute:
            mock_result = MagicMock()
            mock_result.fetchall.return_value = [
                ("Chunk about methodology",),
                ("Chunk about results",),
            ]
            mock_execute.return_value = mock_result

            chunks = rag.retrieve(thesis_id, "methodology", db_session, k=2)
            assert len(chunks) == 2
            assert chunks[0] == "Chunk about methodology"
            mock_embeddings.embed_query.assert_called_once_with("methodology")
