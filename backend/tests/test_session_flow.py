"""Tests for the full Phase 1 session HTTP loop."""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models import Answer, Question, Session, SessionReport
from app.services.session import RUBRIC_CATEGORIES


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_openai_response(content: str):
    """Build a mock OpenAI ChatCompletion response."""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = content
    return mock_resp


STRONG_GRADING = json.dumps({
    "relevance": 9, "depth": 8, "defensibility": 8,
    "overall_score": 8, "triggered_pushback": False,
    "feedback": "Strong answer demonstrating deep understanding.",
})

WEAK_GRADING = json.dumps({
    "relevance": 3, "depth": 2, "defensibility": 2,
    "overall_score": 3, "triggered_pushback": True,
    "feedback": "Vague and lacks depth. Needs follow-up.",
})

REPORT_SUMMARY = json.dumps({
    "strengths": "Good understanding of methodology.",
    "weaknesses": "Weak on related work discussion.",
})


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestCreateSession:

    def test_create_session(self, client, sample_thesis, sample_user):
        response = client.post(
            "/api/sessions",
            json={
                "thesis_id": str(sample_thesis.id),
                "user_id": str(sample_user.id),
                "language": "en",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "in_progress"
        assert body["current_category"] == RUBRIC_CATEGORIES[0]
        assert body["thesis_id"] == str(sample_thesis.id)


class TestNextQuestion:

    @patch("app.services.session._get_openai")
    @patch("app.services.session.retrieve")
    @patch("app.services.session.fetch_related_papers")
    def test_next_question_returns_question(
        self, mock_papers, mock_retrieve, mock_openai,
        client, db_session, sample_thesis, sample_user,
    ):
        # Setup mocks
        mock_retrieve.return_value = ["Context chunk 1", "Context chunk 2"]
        mock_papers.return_value = []

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(
            "Can you explain the problem your thesis addresses?"
        )
        mock_openai.return_value = mock_client

        # Create session
        resp = client.post("/api/sessions", json={
            "thesis_id": str(sample_thesis.id),
            "user_id": str(sample_user.id),
            "language": "en",
        })
        session_id = resp.json()["id"]

        # Get first question
        resp = client.get(f"/api/sessions/{session_id}/next-question")
        assert resp.status_code == 200
        body = resp.json()
        assert body["rubric_category"] == RUBRIC_CATEGORIES[0]
        assert body["sequence_number"] == 1
        assert len(body["text"]) > 0

    @patch("app.services.session._get_openai")
    @patch("app.services.session.retrieve")
    @patch("app.services.session.fetch_related_papers")
    def test_related_work_calls_scholarxiv(
        self, mock_papers, mock_retrieve, mock_openai,
        client, db_session, sample_thesis, sample_user,
    ):
        """When category is 'Related Work', ScholarXIV API should be called."""
        mock_retrieve.return_value = ["Related work context"]
        mock_papers.return_value = [
            {"id": "2401.01234v1", "title": "A Related Paper", "snippet": "Abstract..."},
        ]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(
            "How does your work differ from the approach in 'A Related Paper'?"
        )
        mock_openai.return_value = mock_client

        # Create session and answer questions up to Related Work
        resp = client.post("/api/sessions", json={
            "thesis_id": str(sample_thesis.id),
            "user_id": str(sample_user.id),
            "language": "en",
        })
        session_id = resp.json()["id"]

        # Manually advance through first two categories
        session = db_session.get(Session, uuid.UUID(session_id))
        for i, cat in enumerate(RUBRIC_CATEGORIES[:2]):
            q = Question(
                session_id=session.id, rubric_category=cat,
                text=f"Q about {cat}?", sequence_number=i + 1,
            )
            db_session.add(q)
            db_session.commit()
            db_session.refresh(q)
            a = Answer(
                question_id=q.id, transcript="Good answer", score=8,
                rubric_feedback={}, triggered_pushback=False,
            )
            db_session.add(a)
            db_session.commit()

        # Now next-question should be "Related Work"
        resp = client.get(f"/api/sessions/{session_id}/next-question")
        assert resp.status_code == 200
        assert resp.json()["rubric_category"] == "Related Work"
        mock_papers.assert_called_once()


class TestAnswerGrading:

    @patch("app.services.session._get_openai")
    @patch("app.services.session.retrieve")
    @patch("app.services.session.fetch_related_papers")
    def test_strong_answer_no_pushback(
        self, mock_papers, mock_retrieve, mock_openai,
        client, db_session, sample_thesis, sample_user,
    ):
        mock_retrieve.return_value = ["Context"]
        mock_papers.return_value = []

        mock_client = MagicMock()
        # First call: question generation; Second call: grading
        mock_client.chat.completions.create.side_effect = [
            _mock_openai_response("Explain your methodology."),
            _mock_openai_response(STRONG_GRADING),
        ]
        mock_openai.return_value = mock_client

        # Create session + get question
        resp = client.post("/api/sessions", json={
            "thesis_id": str(sample_thesis.id),
            "user_id": str(sample_user.id),
            "language": "en",
        })
        session_id = resp.json()["id"]
        client.get(f"/api/sessions/{session_id}/next-question")

        # Submit strong answer
        resp = client.post(
            f"/api/sessions/{session_id}/answers",
            json={"transcript": "We used a transformer architecture with cross-attention..."},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["triggered_pushback"] is False
        assert body["score"] == 8

    @patch("app.services.session._get_openai")
    @patch("app.services.session.retrieve")
    @patch("app.services.session.fetch_related_papers")
    def test_weak_answer_triggers_pushback(
        self, mock_papers, mock_retrieve, mock_openai,
        client, db_session, sample_thesis, sample_user,
    ):
        mock_retrieve.return_value = ["Context"]
        mock_papers.return_value = []

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            _mock_openai_response("Explain your methodology."),
            _mock_openai_response(WEAK_GRADING),
        ]
        mock_openai.return_value = mock_client

        resp = client.post("/api/sessions", json={
            "thesis_id": str(sample_thesis.id),
            "user_id": str(sample_user.id),
            "language": "en",
        })
        session_id = resp.json()["id"]
        client.get(f"/api/sessions/{session_id}/next-question")

        # Submit weak answer
        resp = client.post(
            f"/api/sessions/{session_id}/answers",
            json={"transcript": "I don't really know."},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["triggered_pushback"] is True
        assert body["score"] == 3


class TestPushbackFollowup:

    @patch("app.services.session._get_openai")
    @patch("app.services.session.retrieve")
    @patch("app.services.session.fetch_related_papers")
    def test_pushback_stays_in_same_category(
        self, mock_papers, mock_retrieve, mock_openai,
        client, db_session, sample_thesis, sample_user,
    ):
        """After a weak answer, next-question should remain in the same category."""
        mock_retrieve.return_value = ["Context"]
        mock_papers.return_value = []

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            # Q1 generation
            _mock_openai_response("Explain your problem statement."),
            # Q1 grading (weak → pushback)
            _mock_openai_response(WEAK_GRADING),
            # Q2 generation (follow-up in same category)
            _mock_openai_response("Let me rephrase: what specific gap does your work fill?"),
        ]
        mock_openai.return_value = mock_client

        resp = client.post("/api/sessions", json={
            "thesis_id": str(sample_thesis.id),
            "user_id": str(sample_user.id),
            "language": "en",
        })
        session_id = resp.json()["id"]

        # First question
        resp = client.get(f"/api/sessions/{session_id}/next-question")
        first_category = resp.json()["rubric_category"]
        assert first_category == RUBRIC_CATEGORIES[0]

        # Weak answer
        client.post(
            f"/api/sessions/{session_id}/answers",
            json={"transcript": "Umm, I'm not sure."},
        )

        # Next question should stay in same category
        resp = client.get(f"/api/sessions/{session_id}/next-question")
        assert resp.json()["rubric_category"] == first_category


class TestReport:

    @patch("app.services.session._get_openai")
    def test_generate_report(self, mock_openai, client, db_session, sample_thesis, sample_user):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(REPORT_SUMMARY)
        mock_openai.return_value = mock_client

        # Create a session with some answered questions
        session = Session(
            thesis_id=sample_thesis.id,
            user_id=sample_user.id,
            language="en",
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        for i, cat in enumerate(RUBRIC_CATEGORIES[:3]):
            q = Question(
                session_id=session.id, rubric_category=cat,
                text=f"Question about {cat}?", sequence_number=i + 1,
            )
            db_session.add(q)
            db_session.commit()
            db_session.refresh(q)
            a = Answer(
                question_id=q.id, transcript=f"Answer about {cat}",
                score=7 + i, rubric_feedback={}, triggered_pushback=False,
            )
            db_session.add(a)
        db_session.commit()

        # Get report
        resp = client.get(f"/api/sessions/{session.id}/report")
        assert resp.status_code == 200
        body = resp.json()
        assert "overall_score" in body
        assert isinstance(body["overall_score"], int)
        assert "per_category_breakdown" in body
        assert "strengths" in body
        assert "weaknesses" in body

    def test_report_not_found(self, client):
        fake_id = uuid.uuid4()
        resp = client.get(f"/api/sessions/{fake_id}/report")
        assert resp.status_code == 404
