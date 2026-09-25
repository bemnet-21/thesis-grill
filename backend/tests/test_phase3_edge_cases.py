"""Tests for Phase 3 edge-case resilience and graceful degradation."""

import io
import json
import uuid
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.models import Answer, Question, Session, Thesis
from app.services.rag import ingest_thesis
from app.services.session import RUBRIC_CATEGORIES


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_openai_response(content: str):
    """Build a mock OpenAI ChatCompletion response."""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = content
    return mock_resp


# ── Test: ScholarXIV 429 Rate-Limit Fallback ─────────────────────────────────


class TestScholarxivRateLimitFallback:

    @patch("app.services.session._get_openai")
    @patch("app.services.session.retrieve")
    @patch("app.services.scholarxiv.httpx.get")
    def test_scholarxiv_rate_limit_fallback(
        self, mock_httpx_get, mock_retrieve, mock_openai,
        client, db_session, sample_thesis, sample_user,
    ):
        """When ScholarXIV returns 429, the session must not crash —
        /next-question should still return 200 with a valid question."""
        mock_retrieve.return_value = ["Thesis context about related work"]

        # Simulate a 429 response from ScholarXIV
        mock_response = httpx.Response(
            status_code=429,
            request=httpx.Request("GET", "https://scholarxiv.com/api/v1/papers/search"),
        )
        mock_httpx_get.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=mock_response.request,
            response=mock_response,
        )

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(
            "How does your work relate to existing transformer architectures in NLP?"
        )
        mock_openai.return_value = mock_client

        # Create session and advance to "Related Work" category
        session = Session(
            thesis_id=sample_thesis.id,
            user_id=sample_user.id,
            language="en",
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        # Seed answered questions for the first two categories
        for i, cat in enumerate(RUBRIC_CATEGORIES[:2]):
            q = Question(
                session_id=session.id, rubric_category=cat,
                text=f"Q about {cat}?", sequence_number=i + 1,
            )
            db_session.add(q)
            db_session.commit()
            db_session.refresh(q)
            a = Answer(
                question_id=q.id, transcript=f"Good answer about {cat}",
                score=8, rubric_feedback={}, triggered_pushback=False,
            )
            db_session.add(a)
        db_session.commit()

        # Request next question — should be "Related Work" and must not crash
        resp = client.get(f"/api/sessions/{session.id}/next-question")
        assert resp.status_code == 200
        body = resp.json()
        assert body["rubric_category"] == "Related Work"
        assert len(body["text"]) > 0
        # ScholarXIV was called but failed — question was still generated
        mock_httpx_get.assert_called_once()


# ── Test: Empty Retrieval Fallback ────────────────────────────────────────────


class TestEmptyRetrievalFallback:

    @patch("app.services.session._get_openai")
    @patch("app.services.session.retrieve")
    @patch("app.services.session.fetch_related_papers")
    def test_empty_retrieval_fallback(
        self, mock_papers, mock_retrieve, mock_openai,
        client, db_session, sample_thesis, sample_user,
    ):
        """When retrieve() returns zero chunks, the system must fall back
        gracefully (using abstract or generic) and still return a valid question."""
        # Return empty chunks — simulates poor vector search match
        mock_retrieve.return_value = []
        mock_papers.return_value = []

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(
            "Can you walk me through the high-level problem your thesis tackles?"
        )
        mock_openai.return_value = mock_client

        # Create session
        resp = client.post("/api/sessions", json={
            "thesis_id": str(sample_thesis.id),
            "user_id": str(sample_user.id),
            "language": "en",
        })
        assert resp.status_code == 201
        session_id = resp.json()["id"]

        # Get first question — must succeed despite empty retrieval
        resp = client.get(f"/api/sessions/{session_id}/next-question")
        assert resp.status_code == 200
        body = resp.json()
        assert body["rubric_category"] == RUBRIC_CATEGORIES[0]
        assert len(body["text"]) > 0

        # Verify the LLM prompt included the abstract fallback
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        user_msg = messages[1]["content"]
        # sample_thesis has abstract set — should see the fallback text
        assert "abstract" in user_msg.lower() or "No thesis context" in user_msg

    @patch("app.services.session._get_openai")
    @patch("app.services.session.retrieve")
    @patch("app.services.session.fetch_related_papers")
    def test_empty_retrieval_no_abstract(
        self, mock_papers, mock_retrieve, mock_openai,
        client, db_session, sample_user,
    ):
        """When both retrieval and abstract are empty, use generic rubric fallback."""
        mock_retrieve.return_value = []
        mock_papers.return_value = []

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(
            "What is the fundamental problem you set out to solve?"
        )
        mock_openai.return_value = mock_client

        # Create thesis without abstract
        thesis = Thesis(
            user_id=sample_user.id,
            title="Thesis Without Abstract",
            ingestion_status="ready",
            abstract=None,
        )
        db_session.add(thesis)
        db_session.commit()
        db_session.refresh(thesis)

        resp = client.post("/api/sessions", json={
            "thesis_id": str(thesis.id),
            "user_id": str(sample_user.id),
            "language": "en",
        })
        session_id = resp.json()["id"]

        resp = client.get(f"/api/sessions/{session_id}/next-question")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["text"]) > 0

        # Verify generic fallback was used
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        user_msg = messages[1]["content"]
        assert "No thesis context available" in user_msg


# ── Test: Ingestion Failure State ─────────────────────────────────────────────


class TestIngestionFailureState:

    @patch("app.services.rag._get_embeddings")
    @patch("app.services.rag.PyPDFLoader")
    def test_ingestion_failure_state(
        self, mock_loader_cls, mock_get_embeddings, db_session, sample_user,
    ):
        """When PDF parsing fails, ingestion_status must be set to 'failed'
        so the frontend can display an error via GET /status."""
        thesis = Thesis(
            user_id=sample_user.id,
            title="Corrupt PDF Thesis",
            ingestion_status="pending",
        )
        db_session.add(thesis)
        db_session.commit()
        db_session.refresh(thesis)

        # Make the PDF loader crash
        mock_loader = MagicMock()
        mock_loader.load.side_effect = Exception("Corrupt PDF: unable to parse")
        mock_loader_cls.return_value = mock_loader

        # Run ingestion directly (simulating background task)
        ingest_thesis(thesis.id, "/fake/corrupt.pdf", db_session)

        # Verify status is "failed"
        db_session.refresh(thesis)
        assert thesis.ingestion_status == "failed"

    @patch("app.services.rag._get_embeddings")
    @patch("app.services.rag.PyPDFLoader")
    def test_ingestion_failure_visible_via_status_endpoint(
        self, mock_loader_cls, mock_get_embeddings,
        client, db_session, sample_user,
    ):
        """The GET /api/theses/{id}/status endpoint must reflect 'failed' status
        after a corrupt PDF ingestion attempt."""
        thesis = Thesis(
            user_id=sample_user.id,
            title="Corrupt PDF Thesis 2",
            ingestion_status="pending",
        )
        db_session.add(thesis)
        db_session.commit()
        db_session.refresh(thesis)

        mock_loader = MagicMock()
        mock_loader.load.side_effect = RuntimeError("PDF stream error")
        mock_loader_cls.return_value = mock_loader

        ingest_thesis(thesis.id, "/fake/broken.pdf", db_session)

        # Check via HTTP endpoint
        resp = client.get(f"/api/theses/{thesis.id}/status")
        assert resp.status_code == 200
        assert resp.json()["ingestion_status"] == "failed"
