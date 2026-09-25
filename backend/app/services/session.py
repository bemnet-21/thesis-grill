"""Session & rubric engine — question generation, grading, and reports."""

import json
import logging
import uuid

from openai import OpenAI
from sqlalchemy.orm import Session as DBSession

from app.core.config import settings
from app.models import Answer, Question, Session, SessionReport, Thesis
from app.services.rag import retrieve
from app.services.scholarxiv import fetch_related_papers

logger = logging.getLogger(__name__)

RUBRIC_CATEGORIES = [
    "Problem Statement",
    "Methodology",
    "Related Work",
    "Results & Discussion",
    "Contribution",
    "Conclusion",
]

_openai_client = None


def _get_openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
    return _openai_client


# ── Session lifecycle ─────────────────────────────────────────────────────────


def create_session(
    thesis_id: uuid.UUID, user_id: uuid.UUID, language: str, db: DBSession
) -> tuple[Session, str]:
    """Create a new defense session and return it with the first rubric category."""
    session = Session(
        thesis_id=thesis_id,
        user_id=user_id,
        language=language,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session, RUBRIC_CATEGORIES[0]


# ── Category selection ────────────────────────────────────────────────────────


def get_next_category(session: Session, db: DBSession) -> str | None:
    """Determine the next rubric category to cover.

    If the last answer triggered pushback, stay in the same category.
    Otherwise advance to the next uncovered category.
    Returns None when all categories are exhausted.
    """
    questions = (
        db.query(Question)
        .filter(Question.session_id == session.id)
        .order_by(Question.sequence_number)
        .all()
    )

    if not questions:
        return RUBRIC_CATEGORIES[0]

    last_question = questions[-1]
    # Check if the last answer triggered pushback
    if last_question.answer and last_question.answer.triggered_pushback:
        return last_question.rubric_category

    # Collect categories that have been answered without pushback
    covered = set()
    for q in questions:
        if q.answer and not q.answer.triggered_pushback:
            covered.add(q.rubric_category)

    for category in RUBRIC_CATEGORIES:
        if category not in covered:
            return category

    return None  # All categories covered


# ── Language steering ─────────────────────────────────────────────────────────

_LANGUAGE_INSTRUCTIONS = {
    "am": (
        "IMPORTANT: You MUST output your entire response in Amharic (አማርኛ). "
        "Use the Amharic script exclusively. Do not mix in English."
    ),
    "en": (
        "Output your response in English."
    ),
}


def _lang_instruction(language: str) -> str:
    """Return the LLM language-steering instruction for the given session language."""
    return _LANGUAGE_INSTRUCTIONS.get(language, _LANGUAGE_INSTRUCTIONS["en"])


# ── Question generation ───────────────────────────────────────────────────────


def generate_question(
    session: Session, category: str, db: DBSession
) -> Question:
    """Generate a rubric-based question using RAG context and LLM."""
    # 1. Retrieve thesis context for this category
    context_chunks = retrieve(session.thesis_id, category, db, k=4)
    context_text = "\n\n---\n\n".join(context_chunks) if context_chunks else "(no context available)"

    # 2. Conditionally fetch related papers for "Related Work"
    scholarxiv_snippets = ""
    related_paper_ids = None
    if category == "Related Work":
        thesis = db.get(Thesis, session.thesis_id)
        query = thesis.title if thesis else category
        papers = fetch_related_papers(query, limit=3)
        if papers:
            related_paper_ids = [p["id"] for p in papers]
            scholarxiv_snippets = "\n".join(
                f"- [{p['title']}] (ID: {p['id']}): {p['snippet']}"
                for p in papers
            )

    # 3. Gather prior Q&A for continuity
    prior_questions = (
        db.query(Question)
        .filter(Question.session_id == session.id)
        .order_by(Question.sequence_number)
        .all()
    )
    prior_qa = ""
    for pq in prior_questions:
        answer_text = pq.answer.transcript if pq.answer else "(unanswered)"
        prior_qa += f"Q ({pq.rubric_category}): {pq.text}\nA: {answer_text}\n\n"

    # 4. Check if this is a pushback follow-up
    is_followup = any(
        q.rubric_category == category and q.answer and q.answer.triggered_pushback
        for q in prior_questions
    )

    # 5. Compose question via LLM — spoken-conversational style + language steering
    lang_inst = _lang_instruction(session.language)
    system_prompt = (
        "You are a thesis defense examiner conducting a live oral examination. "
        "Generate a single, clear question that sounds natural when spoken aloud — "
        "as if you are talking directly to the student across a table. "
        "Avoid written-text conventions like bullet points, numbering, or overly formal phrasing. "
        "The question should test understanding and critical thinking about their thesis.\n\n"
        f"{lang_inst}"
    )
    user_prompt = f"""Rubric category: {category}
{"This is a FOLLOW-UP probe — the student's previous answer was weak. Ask a sharper, more challenging question that digs deeper into the same topic. Reference what they said before and press harder." if is_followup else ""}

Thesis context:
{context_text}

{f"Related papers from literature:{chr(10)}{scholarxiv_snippets}" if scholarxiv_snippets else ""}

{f"Prior Q&A in this session:{chr(10)}{prior_qa}" if prior_qa else ""}

Generate exactly one examiner question for the "{category}" category. Be specific and reference the thesis content."""

    client = _get_openai()
    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=300,
    )
    question_text = response.choices[0].message.content.strip()

    # 6. Persist
    seq = len(prior_questions) + 1
    question = Question(
        session_id=session.id,
        rubric_category=category,
        text=question_text,
        related_paper_ids=related_paper_ids,
        sequence_number=seq,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


# ── Answer grading ────────────────────────────────────────────────────────────


def grade_answer(
    question_id: uuid.UUID, transcript: str, db: DBSession
) -> Answer:
    """Grade a student's answer using LLM evaluation."""
    question = db.get(Question, question_id)

    system_prompt = (
        "You are a thesis defense evaluator. Grade the student's answer on three dimensions:\n"
        "1. Relevance (0-10): Does it address the question?\n"
        "2. Depth (0-10): Does it show deep understanding?\n"
        "3. Defensibility (0-10): Could it withstand scrutiny?\n\n"
        "Return a JSON object with keys: relevance, depth, defensibility, overall_score (1-10), "
        "triggered_pushback (boolean — true if the answer is weak and needs follow-up), "
        "and feedback (string with brief examiner notes)."
    )
    user_prompt = f"""Question ({question.rubric_category}): {question.text}

Student's answer: {transcript}

Evaluate and return JSON only."""

    client = _get_openai()
    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=300,
        response_format={"type": "json_object"},
    )

    try:
        grading = json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, IndexError):
        grading = {
            "relevance": 5, "depth": 5, "defensibility": 5,
            "overall_score": 5, "triggered_pushback": False,
            "feedback": "Grading parse error — default score assigned.",
        }

    score = int(grading.get("overall_score", 5))
    triggered_pushback = bool(grading.get("triggered_pushback", False))

    answer = Answer(
        question_id=question_id,
        transcript=transcript,
        score=score,
        rubric_feedback=grading,
        triggered_pushback=triggered_pushback,
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)
    return answer


# ── Hint generation ───────────────────────────────────────────────────────────


def generate_hint(
    session: Session, db: DBSession
) -> str:
    """Generate a small spoken hint for the current unanswered question."""
    # Find the most recent unanswered question
    question = (
        db.query(Question)
        .filter(Question.session_id == session.id, Question.answer == None)  # noqa: E711
        .order_by(Question.sequence_number.desc())
        .first()
    )
    if question is None:
        return "You've already answered all the questions so far."

    # Retrieve context for the hint
    context_chunks = retrieve(session.thesis_id, question.rubric_category, db, k=3)
    context_text = "\n\n".join(context_chunks) if context_chunks else "(no context)"

    lang_inst = _lang_instruction(session.language)
    system_prompt = (
        "You are a supportive thesis defense coach. The student is stuck on an oral exam question. "
        "Give a brief, spoken-style hint — one or two sentences — that nudges them toward the right "
        "direction without revealing the full answer. Sound encouraging and natural.\n\n"
        f"{lang_inst}"
    )
    user_prompt = f"""The question is: {question.text}

Relevant thesis context:
{context_text}

Provide a short hint."""

    client = _get_openai()
    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.6,
        max_tokens=150,
    )
    return response.choices[0].message.content.strip()


# ── Session end ───────────────────────────────────────────────────────────────


def end_session(session: Session, db: DBSession) -> SessionReport:
    """Mark the session completed and trigger early report generation."""
    report = generate_report(session.id, db)
    return report


# ── Report generation ─────────────────────────────────────────────────────────


def generate_report(session_id: uuid.UUID, db: DBSession) -> SessionReport:
    """Aggregate scores and generate a session report."""
    session = db.get(Session, session_id)

    # Gather all answered questions
    questions = (
        db.query(Question)
        .filter(Question.session_id == session_id)
        .order_by(Question.sequence_number)
        .all()
    )

    # Build per-category breakdown
    category_scores: dict[str, list[int]] = {}
    all_scores: list[int] = []
    qa_summary = ""

    for q in questions:
        if not q.answer:
            continue
        cat = q.rubric_category
        category_scores.setdefault(cat, []).append(q.answer.score)
        all_scores.append(q.answer.score)
        qa_summary += (
            f"Category: {cat}\n"
            f"Q: {q.text}\n"
            f"A: {q.answer.transcript}\n"
            f"Score: {q.answer.score}/10\n\n"
        )

    per_category = {
        cat: round(sum(scores) / len(scores), 1)
        for cat, scores in category_scores.items()
    }
    overall_score = round(sum(all_scores) / len(all_scores)) if all_scores else 0

    # LLM summary of strengths and weaknesses
    client = _get_openai()
    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Summarize the student's thesis defense performance. "
                    "Return JSON with keys: strengths (string), weaknesses (string)."
                ),
            },
            {
                "role": "user",
                "content": f"Per-category scores: {json.dumps(per_category)}\n\n{qa_summary}",
            },
        ],
        temperature=0.3,
        max_tokens=400,
        response_format={"type": "json_object"},
    )

    try:
        summary = json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, IndexError):
        summary = {
            "strengths": "Could not generate summary.",
            "weaknesses": "Could not generate summary.",
        }

    # Mark session as completed
    from datetime import datetime, timezone

    session.status = "completed"
    session.ended_at = datetime.now(timezone.utc)

    report = SessionReport(
        session_id=session_id,
        overall_score=overall_score,
        per_category_breakdown=per_category,
        strengths=summary.get("strengths", ""),
        weaknesses=summary.get("weaknesses", ""),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
