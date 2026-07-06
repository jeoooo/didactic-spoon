# AI Resume Screener API - Technical Spec

## 1. Overview

A backend service that scores how well a resume matches a job description and returns a structured, explainable breakdown. Built to demonstrate Python and FastAPI competence for backend/AI-adjacent roles.

The core value is not "call an LLM." It is turning a fuzzy matching problem into a typed, validated, well-structured API with sensible engineering around it: input validation, structured LLM output, caching, error handling, and tests. That is what a screener looking for Python backend skills wants to see.

**Primary goal:** portfolio piece that proves production-grade Python backend skills.
**Secondary goal:** genuinely useful during a job search.

**Remote repository:** `https://github.com/jeoooo/didactic-spoon.git`

## 2. Scope

### In scope (MVP)
- Accept a resume (PDF upload or raw text) and a job description (text).
- Extract text from the PDF.
- Send both to an LLM and get back a structured match analysis.
- Return a match score (0 to 100), matched skills, missing skills, and short reasoning.
- Persist each analysis so results can be retrieved later by ID.
- Cache identical resume plus JD pairs to avoid duplicate LLM calls.

### Out of scope (for MVP)
- User accounts and auth.
- Multi-resume ranking against one JD (stretch goal).
- A polished frontend (a thin demo UI is a separate optional layer).
- Fine-tuning or any ML training. This is prompt-driven.

## 3. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.12+ | Target skill to demonstrate |
| Framework | FastAPI | Async, typed, auto OpenAPI docs, screener-recognized |
| Validation | Pydantic v2 | Typed request/response models, structured LLM parsing |
| PDF parsing | pypdf (or pdfplumber for messy layouts) | Text extraction |
| LLM | OpenCode Go (OpenAI-compatible endpoint) | One key, open models (Kimi, GLM, Qwen, DeepSeek), swappable behind an interface |
| Storage | PostgreSQL via SQLAlchemy 2.0 | Production-standard, what Python job listings expect |
| DB driver | psycopg (v3) | Modern Postgres driver for SQLAlchemy |
| Migrations | Alembic | Schema versioning, a signal of production maturity |
| Cache | In-memory dict (MVP) or Redis | Avoid duplicate LLM calls |
| Testing | pytest, httpx AsyncClient | API and unit tests |
| Deploy | Railway or Render | Simple Python deploys, both offer managed Postgres |

Keep the LLM provider behind a small interface (a `ScoringProvider` protocol) so switching providers is a one-file change. You are using OpenCode Go now, but the abstraction means you can drop in a direct Claude or OpenAI call later without touching the rest of the app. This is a good thing to point to in interviews, and it is a stronger design signal than hardcoding one vendor.

## 4. API Design

### `POST /api/v1/analyze`
Submit a resume and job description for scoring.

**Request** (multipart if PDF, JSON if text):
```
resume_file: UploadFile   (optional, PDF)
resume_text: str          (optional, used if no file)
job_description: str       (required)
```
Exactly one of `resume_file` or `resume_text` must be provided.

**Response** `200 OK`:
```json
{
  "id": "a1b2c3d4",
  "match_score": 78,
  "summary": "Strong backend fit, light on the required cloud experience.",
  "matched_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
  "missing_skills": ["Kubernetes", "GraphQL"],
  "strengths": ["3 years shipping typed backends", "CI/CD experience"],
  "gaps": ["No named Kubernetes experience"],
  "cached": false,
  "created_at": "2026-07-06T10:00:00Z"
}
```

### `GET /api/v1/analyze/{id}`
Retrieve a past analysis by ID. Returns the same shape, or `404` if not found.

### `GET /api/v1/health`
Liveness check. Returns `{"status": "ok"}`.

Errors use standard HTTP codes with a consistent JSON body:
```json
{ "error": "validation_error", "detail": "job_description is required" }
```
Handle at minimum: missing inputs (422), unparseable PDF (422), LLM failure/timeout (502), not found (404).

## 5. Data Models (Pydantic + DB)

**Pydantic response model** (`AnalysisResult`): mirrors the response above. This same model is what you ask the LLM to populate, which gives you free validation of the LLM output.

**DB table** (`analyses`), PostgreSQL:
```
id              TEXT PRIMARY KEY        (short uuid)
resume_hash     TEXT NOT NULL           (sha256 of resume text, for cache lookup)
jd_hash         TEXT NOT NULL           (sha256 of job description)
match_score     INTEGER NOT NULL
result_json     JSONB NOT NULL          (full AnalysisResult; JSONB, not TEXT)
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
```
Use a composite index on `(resume_hash, jd_hash)` for the cache lookup. Storing the result as `JSONB` (rather than serialized text) is the idiomatic Postgres choice and lets you query into the result later if you want. Manage the schema with an Alembic migration rather than creating tables by hand, which is the production-standard pattern reviewers look for.

## 6. LLM Integration (OpenCode Go)

You are routing the AI scoring through OpenCode Go using its OpenAI-compatible endpoint. Because it speaks the standard OpenAI chat completions format, you can use the official `openai` Python SDK and just point it at the OpenCode base URL.

### Setup
- Get your key from the OpenCode dashboard and store it as `OPENCODE_API_KEY` in `.env` (never commit it).
- Grab the exact base URL from the OpenCode Go docs (opencode.ai/docs/go). It exposes an OpenAI-compatible chat completions endpoint.
- Model IDs use the `opencode-go/<model-id>` format. For this task a solid general model like `opencode-go/kimi-k2.7-code`, `opencode-go/glm-5.2`, or a DeepSeek variant works well. Put the model id in config so you can swap it without code changes.

### Client wiring
```python
from openai import OpenAI

client = OpenAI(
    api_key=settings.opencode_api_key,
    base_url=settings.opencode_base_url,  # OpenCode Go OpenAI-compatible endpoint
)

resp = client.chat.completions.create(
    model=settings.model_id,  # e.g. "opencode-go/kimi-k2.7-code"
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ],
    temperature=0.2,
)
```
This lives inside your `OpenCodeScoringProvider`, which implements the `ScoringProvider` protocol. Nothing else in the app knows or cares which provider is behind it.

### Prompt shape
- System: "You are a technical recruiter. Score the resume against the job description. Return only valid JSON matching this schema. Do not invent skills the resume does not support."
- User: the resume text and the job description, clearly delimited.

### Structured output caveat (important with open models)
The open models on OpenCode Go are strong but less rigorously tuned for strict JSON-only output than the big proprietary models, and not all of them support a native JSON/structured-output mode. So do not rely on the model being perfectly well-behaved. Build defensively:
- Instruct hard for JSON only, and extract the JSON substring from the response before parsing (strip any markdown fences or stray prose the model adds).
- Parse into the `AnalysisResult` Pydantic model. On validation failure, retry once with a stricter "return ONLY the JSON object, nothing else" instruction.
- If it still fails, surface a clean 502. Keep low `temperature` (around 0.2) for more consistent structure.
- Pick a capable model id and pin it in config; if one model is flaky on JSON, swapping to another is a config change, not a rewrite. This "resilient parsing across a less predictable model" story is itself a good interview talking point.

### General guardrails (mention these in your README)
- Cap input length (truncate very long resumes/JDs before sending).
- Fully stripping prompt-injection from resume text is hard, but at minimum delimit clearly and instruct the model to treat resume content as data, not instructions.
- Validate `match_score` is an int in 0 to 100; clamp if out of range.

### Deployment note
Your OpenCode Go key is a personal subscription tied to your quota. That is fine for a portfolio demo, but if you deploy this publicly, every visitor's request burns your allocation. Two easy mitigations: keep the live demo behind a simple rate limit, or have the deployed demo fall back to a "paste your own key" field. For interviews, running it locally during a screen share sidesteps this entirely.

## 7. Project Structure

```
resume-screener/
  app/
    main.py              # FastAPI app, router registration
    config.py            # settings via pydantic-settings (OPENCODE_API_KEY, base URL, model id, DATABASE_URL)
    api/
      routes.py          # endpoint handlers
    core/
      pdf.py             # PDF text extraction
      scoring.py         # ScoringProvider protocol + OpenCodeScoringProvider impl
      cache.py           # hash-based cache lookup
    models/
      schemas.py         # Pydantic request/response models
      db.py              # SQLAlchemy 2.0 models + session/engine
  alembic/
    versions/            # migration scripts
  alembic.ini
  tests/
    conftest.py          # test DB fixture (Postgres, e.g. testcontainers or a test schema)
    test_analyze.py
    test_pdf.py
    test_scoring.py      # mock the LLM, assert parsing/validation
  .env.example
  requirements.txt
  docker-compose.yml     # local Postgres for dev
  Dockerfile
  README.md
```

### requirements.txt
```
fastapi
uvicorn[standard]
pydantic
pydantic-settings
python-multipart          # required for file uploads in FastAPI
sqlalchemy>=2.0
psycopg[binary]           # Postgres driver (v3)
alembic
pypdf
openai                    # used against the OpenCode Go OpenAI-compatible endpoint
python-dotenv
pytest
pytest-asyncio
httpx
```
Pin versions once it runs (`pip freeze > requirements.txt`) so the build is reproducible. If you prefer pdfplumber over pypdf for messier resume layouts, swap that line. Keep test-only deps here for simplicity, or split them into `requirements-dev.txt` if you want to look tidy.

## 8. Testing

Mock the LLM call in tests (do not hit the real API in CI). Cover:
- Happy path: valid resume + JD returns a well-formed result.
- Missing job description returns 422.
- Both file and text provided, or neither, returns 422.
- Malformed LLM output triggers the retry, then 502 if still bad.
- Cache hit returns `cached: true` without calling the LLM (assert the mock was not called).

Good test coverage is a strong signal on a portfolio project, so this is worth doing properly rather than skipping.

## 9. README (matters as much as the code)

For a portfolio piece the README is what the screener reads first. Include:
- One-line pitch and a screenshot or a short GIF of the demo.
- Live demo link (Railway/Render) plus the auto-generated `/docs` Swagger link.
- Quickstart: clone, set env, run in 3 commands.
- Architecture note: why the provider is swappable, how caching works, how LLM output is validated.
- Example curl request and response.

## 10. Stretch Goals (after MVP ships)

- Thin demo UI: single page (React or SvelteKit, both in your wheelhouse), upload PDF, paste JD, see the score. About 2 to 3 hours, makes it link-shareable.
- Rank multiple resumes against one JD, sorted by score.
- Swap in Redis for the cache to show the pattern.
- Add rate limiting (slowapi) as a production-readiness signal.
- Dockerize and add a GitHub Actions CI workflow running the tests.

## 11. Suggested Build Order

Each numbered step is one logical unit of work and maps to one commit (see Commit Convention below).

1. Skeleton FastAPI app with `/health`, `docker-compose.yml` for local Postgres, and a Dockerfile.
2. Pydantic schemas for request and response.
3. PDF text extraction with a couple of test fixtures.
4. Scoring provider against OpenCode Go, returning validated structured output.
5. Wire `POST /analyze` end to end (no cache, no DB yet).
6. Add SQLAlchemy models + Alembic migration, Postgres persistence, and `GET /analyze/{id}`.
7. Add hash-based caching.
8. Tests across the board.
9. Deploy, write the README, record a demo GIF.
10. Optional: thin UI, then the other stretch goals.

Aim to have steps 1 through 9 done in a weekend. That is a shippable, demoable Python backend you can point any recruiter to.

## 12. Commit Convention

- **Remote:** `https://github.com/jeoooo/didactic-spoon.git`. Initialize and wire it up before the first commit:
  ```
  git init
  git remote add origin https://github.com/jeoooo/didactic-spoon.git
  git branch -M main
  # first commit, then:
  git push -u origin main
  ```
- **One logical change per commit.** Each build-order step (and each stretch goal) is its own commit. Keep unrelated changes out of the same commit so `git log` reads like a clean build narrative.
- **No AI co-author trailer.** Do not append `Co-Authored-By` or any AI-tool attribution to commit messages. If your tooling adds it automatically, disable it. In Claude Code you can turn off the trailer in settings; more generally, check that nothing appends a `Co-Authored-By:` line in your commit template or tool config.
- **Conventional-style messages** read well on a portfolio: `feat: add PDF text extraction`, `feat: wire POST /analyze end to end`, `test: cover cache hit path`, `chore: pin requirements`, `docs: write README`.
- **Suggested commit sequence:**
  ```
  chore: scaffold FastAPI app, health check, docker-compose Postgres
  feat: add request/response Pydantic schemas
  feat: add PDF text extraction
  feat: add OpenCode Go scoring provider with validated output
  feat: wire POST /analyze end to end
  feat: add Postgres persistence and GET /analyze/{id}
  feat: add hash-based response caching
  test: cover analyze, pdf, and scoring paths
  docs: write README and add demo
  ```

A note on the dates: I'd commit with real dates as you build. A genuine weekend history is a clean, honest signal, and for someone whose brand is AI-assisted development, shipping fast is the story you want, not something to disguise. Backdating to fabricate a longer timeline tends to leave the committer date at the real date while only the author date moves, so the two disagree and the manufactured history is visible to anyone who inspects it, which is a worse outcome on a project meant to build trust. Let the real history stand.