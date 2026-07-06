# AI Resume Screener API

Scores how well a resume matches a job description and returns a structured,
explainable breakdown: a match score, matched/missing skills, strengths, and
gaps. Built with FastAPI, Pydantic v2, SQLAlchemy 2.0, and an OpenAI-compatible
LLM backend, with the LLM provider kept behind a small interface so it's a
one-file swap to another vendor.

> Live demo: not yet deployed. Auto-generated API docs are available at
> `/docs` once running locally (see Quickstart).

## Quickstart

```bash
git clone https://github.com/jeoooo/didactic-spoon.git
cd didactic-spoon
cp .env.example .env   # fill in OPENCODE_API_KEY
docker compose up -d   # starts local Postgres
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` for interactive Swagger docs.

## Architecture

- **Swappable LLM provider.** `ScoringProvider` (`app/core/scoring.py`) is a
  `Protocol`; `OpenCodeScoringProvider` is the only implementation today,
  talking to OpenCode Go's OpenAI-compatible endpoint via the official
  `openai` SDK. Nothing else in the app knows which vendor is behind it, so
  swapping to a direct Claude or OpenAI call later is a one-file change.
- **Defensive structured output.** Open models aren't as reliably
  JSON-only as the big proprietary ones. The provider strips markdown fences
  and stray prose, extracts the JSON substring, and validates it against a
  Pydantic model. On failure it retries once with a stricter "JSON only"
  instruction; if that still fails, the API returns a clean `502` rather than
  crashing on bad input.
- **Caching.** Each `(resume, job description)` pair is hashed (SHA-256) and
  looked up before calling the LLM. A cache hit returns the prior result with
  `cached: true` and never touches the LLM, saving quota and latency on
  duplicate submissions.
- **Persistence.** Every analysis is stored in Postgres as JSONB, keyed by a
  short id, so results can be retrieved later via `GET /api/v1/analyze/{id}`.
  Schema is managed with Alembic rather than created ad hoc.

## Example request

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -F "job_description=Looking for a backend engineer with Python, FastAPI, and cloud experience." \
  -F "resume_text=3 years building typed Python backends with FastAPI and PostgreSQL. Shipped CI/CD pipelines."
```

```json
{
  "id": "a1b2c3d4",
  "match_score": 78,
  "summary": "Strong backend fit, light on the required cloud experience.",
  "matched_skills": ["Python", "FastAPI", "PostgreSQL"],
  "missing_skills": ["Kubernetes", "GraphQL"],
  "strengths": ["3 years shipping typed backends", "CI/CD experience"],
  "gaps": ["No named Kubernetes experience"],
  "cached": false,
  "created_at": "2026-07-06T10:00:00Z"
}
```

Or submit a PDF instead of `resume_text`:

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -F "job_description=Looking for a backend engineer." \
  -F "resume_file=@resume.pdf;type=application/pdf"
```

Fetch a past result:

```bash
curl http://localhost:8000/api/v1/analyze/a1b2c3d4
```

## Guardrails

- Resume/JD input is truncated before being sent to the LLM (configurable via
  `MAX_RESUME_CHARS` / `MAX_JD_CHARS`).
- Resume content is delimited and the model is instructed to treat it as data,
  not instructions, to reduce prompt-injection risk (not a complete defense).
- `match_score` is validated as an int 0-100 and clamped if the model returns
  something out of range.

## Testing

```bash
pytest
```

Tests mock the LLM call (no real API traffic in CI) and run against an
in-memory SQLite database standing in for Postgres. Coverage includes the
happy path (text and PDF resumes), missing/duplicate input validation,
malformed-LLM-output retry and fallback to `502`, and the cache-hit path
(asserting the mock LLM is not called twice).

## Project layout

```
app/
  main.py          FastAPI app, exception handlers
  config.py        Settings (env-driven)
  api/routes.py     Endpoint handlers
  core/
    pdf.py          PDF text extraction
    scoring.py       ScoringProvider protocol + OpenCode Go implementation
    cache.py         Hash-based cache lookup
    hashing.py, ids.py, errors.py, deps.py
  models/
    schemas.py       Pydantic request/response models
    db.py            SQLAlchemy models + async engine/session
alembic/             Migrations
tests/
```
