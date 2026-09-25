"""Tests for Phase 2 conversational voice-driven backend logic."""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models import Answer, Question, Session
from app.services.session import RUBRIC_CATEGORIES


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_openai_response(content: str):
    """Build a mock OpenAI ChatCompletion response."""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = content
    return mock_resp


WEAK_GRADING = json.dumps({
    "relevance": 3, "depth": 2, "defensibility": 2,
    "overall_score": 3, "triggered_pushback": True,
    "feedback": "Vague and lacks depth. Needs follow-up.",
})

STRONG_GRADING = json.dumps({
    "relevance": 9, "depth": 8, "defensibility": 8,
    "overall_score": 8, "triggered_pushback": False,
    "feedback": "Strong answer demonstrating deep understanding.",
})

REPORT_SUMMARY = json.dumps({
    "strengths": "Good understanding of methodology.",
    "weaknesses": "Weak on related work discussion.",
})


# ── Test: Pushback Loop ──────────────────────────────────────────────────────


class TestPushbackLoop:

    @patch("app.services.session._get_openai")
    @patch("app.services.session.retrieve")
    @patch("app.services.session.fetch_related_papers")
    def test_pushback_loop(
        self, mock_papers, mock_retrieve, mock_openai,
        client, db_session, sample_thesis, sample_user,
    ):
        """Submit a weak answer → next-question stays in the same rubric category."""
        mock_retrieve.return_value = ["Context chunk"]
        mock_papers.return_value = []

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            # Q1 generation
            _mock_openai_response("What is the core problem your thesis addresses?"),
            # Q1 grading (weak → pushback)
            _mock_openai_response(WEAK_GRADING),
            # Q2 generation (follow-up in same category)
            _mock_openai_response("You mentioned the problem is unclear — can you be more specific about the research gap?"),
        ]
        mock_openai.return_value = mock_client

        # Create session
        resp = client.post("/api/sessions", json={
            "thesis_id": str(sample_thesis.id),
            "user_id": str(sample_user.id),
            "language": "en",
        })
        assert resp.status_code == 201
        session_id = resp.json()["id"]

        # Get first question
        resp = client.get(f"/api/sessions/{session_id}/next-question")
        assert resp.status_code == 200
        first_category = resp.json()["rubric_category"]
        assert first_category == RUBRIC_CATEGORIES[0]

        # Submit weak answer → triggers pushback
        resp = client.post(
            f"/api/sessions/{session_id}/answers",
            json={"transcript": "I don't really know."},
        )
        assert resp.status_code == 200
        assert resp.json()["triggered_pushback"] is True

        # Next question should stay in the SAME category
        resp = client.get(f"/api/sessions/{session_id}/next-question")
        assert resp.status_code == 200
        followup_category = resp.json()["rubric_category"]
        assert followup_category == first_category, (
            f"Expected pushback to keep category '{first_category}', "
            f"but got '{followup_category}'"
        )


# ── Test: Language Steering ──────────────────────────────────────────────────


class TestLanguageSteering:

    @patch("app.services.session._get_openai")
    @patch("app.services.session.retrieve")
    @patch("app.services.session.fetch_related_papers")
    def test_language_steering_amharic(
        self, mock_papers, mock_retrieve, mock_openai,
        client, db_session, sample_thesis, sample_user,
    ):
        """Session with language='am' should include Amharic instruction in the LLM prompt."""
        mock_retrieve.return_value = ["Context chunk"]
        mock_papers.return_value = []

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(
            "የጽሑፍዎ ዋና ችግር ምንድን ነው?"
        )
        mock_openai.return_value = mock_client

        # Create session with Amharic language
        resp = client.post("/api/sessions", json={
            "thesis_id": str(sample_thesis.id),
            "user_id": str(sample_user.id),
            "language": "am",
        })
        assert resp.status_code == 201
        session_id = resp.json()["id"]

        # Get first question
        resp = client.get(f"/api/sessions/{session_id}/next-question")
        assert resp.status_code == 200

        # Verify the LLM was called with Amharic steering in the system prompt
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        system_msg = messages[0]["content"]
        assert "Amharic" in system_msg, (
            "System prompt should contain Amharic language instruction"
        )
        assert "አማርኛ" in system_msg, (
            "System prompt should contain the Amharic script identifier"
        )

    @patch("app.services.session._get_openai")
    @patch("app.services.session.retrieve")
    @patch("app.services.session.fetch_related_papers")
    def test_language_steering_english(
        self, mock_papers, mock_retrieve, mock_openai,
        client, db_session, sample_thesis, sample_user,
    ):
        """Session with language='en' should include English instruction in the LLM prompt."""
        mock_retrieve.return_value = ["Context chunk"]
        mock_papers.return_value = []

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(
            "What is the core problem statement of your thesis?"
        )
        mock_openai.return_value = mock_client

        # Create session with English language
        resp = client.post("/api/sessions", json={
            "thesis_id": str(sample_thesis.id),
            "user_id": str(sample_user.id),
            "language": "en",
        })
        session_id = resp.json()["id"]

        resp = client.get(f"/api/sessions/{session_id}/next-question")
        assert resp.status_code == 200

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        system_msg = messages[0]["content"]
        assert "English" in system_msg


# ── Test: Request Hint ───────────────────────────────────────────────────────


class TestRequestHint:

    @patch("app.services.session._get_openai")
    @patch("app.services.session.retrieve")
    @patch("app.services.session.fetch_related_papers")
    def test_request_hint(
        self, mock_papers, mock_retrieve, mock_openai,
        client, db_session, sample_thesis, sample_user,
    ):
        """GET /hint returns a 200 with a populated hint text."""
        mock_retrieve.return_value = ["Context chunk about methodology"]
        mock_papers.return_value = []

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            # Question generation
            _mock_openai_response("Explain the methodology used in your thesis."),
            # Hint generation
            _mock_openai_response("Think about the specific technique you used for data collection — that's a good starting point."),
        ]
        mock_openai.return_value = mock_client

        # Create session + get question (so there's an unanswered question)
        resp = client.post("/api/sessions", json={
            "thesis_id": str(sample_thesis.id),
            "user_id": str(sample_user.id),
            "language": "en",
        })
        session_id = resp.json()["id"]
        client.get(f"/api/sessions/{session_id}/next-question")

        # Request hint
        resp = client.get(f"/api/sessions/{session_id}/hint")
        assert resp.status_code == 200
        body = resp.json()
        assert "text" in body
        assert len(body["text"]) > 0

    def test_hint_session_not_found(self, client):
        """GET /hint for a nonexistent session returns 404."""
        resp = client.get(f"/api/sessions/{uuid.uuid4()}/hint")
        assert resp.status_code == 404


# ── Test: End Session ────────────────────────────────────────────────────────


class TestEndSession:

    @patch("app.services.session._get_openai")
    def test_end_session(
        self, mock_openai, client, db_session, sample_thesis, sample_user,
    ):
        """POST /end marks session completed and returns report data."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(
            REPORT_SUMMARY
        )
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

        for i, cat in enumerate(RUBRIC_CATEGORIES[:2]):
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

        # End session
        resp = client.post(f"/api/sessions/{session.id}/end")
        assert resp.status_code == 200
        body = resp.json()
        assert "overall_score" in body
        assert isinstance(body["overall_score"], int)
        assert "per_category_breakdown" in body
        assert "strengths" in body
        assert "weaknesses" in body

        # Verify session status was updated
        db_session.refresh(session)
        assert session.status == "completed"
        assert session.ended_at is not None

    def test_end_session_not_found(self, client):
        """POST /end for a nonexistent session returns 404."""
        resp = client.post(f"/api/sessions/{uuid.uuid4()}/end")
        assert resp.status_code == 404

    @patch("app.services.session._get_openai")
    def test_end_session_already_completed(
        self, mock_openai, client, db_session, sample_thesis, sample_user,
    ):
        """POST /end on an already-completed session returns 400."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(
            REPORT_SUMMARY
        )
        mock_openai.return_value = mock_client

        session = Session(
            thesis_id=sample_thesis.id,
            user_id=sample_user.id,
            language="en",
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        # End it once
        q = Question(
            session_id=session.id, rubric_category="Problem Statement",
            text="Q?", sequence_number=1,
        )
        db_session.add(q)
        db_session.commit()
        db_session.refresh(q)
        a = Answer(
            question_id=q.id, transcript="A", score=7,
            rubric_feedback={}, triggered_pushback=False,
        )
        db_session.add(a)
        db_session.commit()

        resp = client.post(f"/api/sessions/{session.id}/end")
        assert resp.status_code == 200

        # Second end should fail
        resp = client.post(f"/api/sessions/{session.id}/end")
        assert resp.status_code == 400
