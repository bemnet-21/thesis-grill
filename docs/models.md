# Data Models Reference

Detailed reference for all database entities in MeRmra Exam.

## User

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `UUID` | PK, auto-generated |
| `name` | `VARCHAR(255)` | NOT NULL |
| `email` | `VARCHAR(255)` | NOT NULL, UNIQUE |
| `institution` | `VARCHAR(255)` | nullable |
| `preferred_language` | `VARCHAR(10)` | nullable |

**Relationships:** has many `Thesis`, has many `Session`

---

## Thesis

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `UUID` | PK, auto-generated |
| `user_id` | `UUID` | FK → `users.id`, NOT NULL |
| `title` | `VARCHAR(500)` | NOT NULL |
| `uploaded_pdf_url` | `TEXT` | nullable |
| `ingestion_status` | `ENUM` | NOT NULL, default `pending` |
| `abstract` | `TEXT` | nullable |

**Enum values for `ingestion_status`:** `pending`, `chunked`, `embedded`, `ready`, `failed`

**Relationships:** belongs to `User`, has many `ThesisChunk`, has many `Session`

---

## ThesisChunk

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `UUID` | PK, auto-generated |
| `thesis_id` | `UUID` | FK → `theses.id`, NOT NULL |
| `section_label` | `VARCHAR(255)` | nullable |
| `text` | `TEXT` | NOT NULL |
| `embedding` | `Vector(1536)` | nullable, pgvector |

**Relationships:** belongs to `Thesis`

---

## Session

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `UUID` | PK, auto-generated |
| `thesis_id` | `UUID` | FK → `theses.id`, NOT NULL |
| `user_id` | `UUID` | FK → `users.id`, NOT NULL |
| `language` | `ENUM` | NOT NULL |
| `status` | `ENUM` | NOT NULL, default `in_progress` |
| `started_at` | `TIMESTAMPTZ` | NOT NULL, auto |
| `ended_at` | `TIMESTAMPTZ` | nullable |

**Enum values for `language`:** `am`, `en`
**Enum values for `status`:** `in_progress`, `completed`, `abandoned`

**Relationships:** belongs to `User`, belongs to `Thesis`, has many `Question`, has one `SessionReport`

---

## Question

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `UUID` | PK, auto-generated |
| `session_id` | `UUID` | FK → `sessions.id`, NOT NULL |
| `rubric_category` | `VARCHAR(255)` | NOT NULL |
| `text` | `TEXT` | NOT NULL |
| `related_paper_ids` | `ARRAY(VARCHAR)` | nullable |
| `sequence_number` | `INTEGER` | NOT NULL |

**Relationships:** belongs to `Session`, has one `Answer`

---

## Answer

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `UUID` | PK, auto-generated |
| `question_id` | `UUID` | FK → `questions.id`, NOT NULL |
| `transcript` | `TEXT` | NOT NULL |
| `score` | `INTEGER` | NOT NULL |
| `rubric_feedback` | `JSONB` | nullable |
| `triggered_pushback` | `BOOLEAN` | NOT NULL, default `false` |

**Relationships:** belongs to `Question`

---

## SessionReport

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `UUID` | PK, auto-generated |
| `session_id` | `UUID` | FK → `sessions.id`, NOT NULL, UNIQUE |
| `overall_score` | `INTEGER` | NOT NULL |
| `per_category_breakdown` | `JSONB` | nullable |
| `strengths` | `TEXT` | nullable |
| `weaknesses` | `TEXT` | nullable |

**Relationships:** belongs to `Session` (one-to-one)
