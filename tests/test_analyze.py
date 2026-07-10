from pathlib import Path

from app.core.scoring import ScoringError
from app.models.schemas import LLMAnalysis

FIXTURES = Path(__file__).parent / "fixtures"

VALID_ANALYSIS = LLMAnalysis(
    match_score=78,
    summary="Strong backend fit, light on cloud experience.",
    matched_skills=["Python", "FastAPI", "PostgreSQL"],
    missing_skills=["Kubernetes"],
    strengths=["3 years shipping typed backends"],
    gaps=["No named Kubernetes experience"],
)


async def test_happy_path_text_resume(client, mock_scoring_provider):
    mock_scoring_provider.score.return_value = VALID_ANALYSIS

    resp = await client.post(
        "/api/v1/analyze",
        data={
            "job_description": "Looking for a Python backend engineer.",
            "resume_text": "I have 3 years of Python and FastAPI experience.",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["match_score"] == 78
    assert body["cached"] is False
    assert body["matched_skills"] == ["Python", "FastAPI", "PostgreSQL"]
    mock_scoring_provider.score.assert_called_once()


async def test_happy_path_pdf_resume(client, mock_scoring_provider):
    mock_scoring_provider.score.return_value = VALID_ANALYSIS
    pdf_bytes = (FIXTURES / "sample_resume.pdf").read_bytes()

    resp = await client.post(
        "/api/v1/analyze",
        data={"job_description": "Looking for a Python backend engineer."},
        files={"resume_file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )

    assert resp.status_code == 200
    assert resp.json()["match_score"] == 78


async def test_missing_job_description_returns_422(client):
    resp = await client.post(
        "/api/v1/analyze",
        data={"resume_text": "some resume text"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_error"


async def test_missing_resume_returns_422(client):
    resp = await client.post(
        "/api/v1/analyze",
        data={"job_description": "Looking for a Python backend engineer."},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_error"


async def test_both_file_and_text_returns_422(client):
    pdf_bytes = (FIXTURES / "sample_resume.pdf").read_bytes()
    resp = await client.post(
        "/api/v1/analyze",
        data={
            "job_description": "Looking for a Python backend engineer.",
            "resume_text": "some resume text",
        },
        files={"resume_file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_error"


async def test_unparseable_pdf_returns_422(client):
    corrupt_bytes = (FIXTURES / "corrupt.pdf").read_bytes()
    resp = await client.post(
        "/api/v1/analyze",
        data={"job_description": "Looking for a Python backend engineer."},
        files={"resume_file": ("resume.pdf", corrupt_bytes, "application/pdf")},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_error"


async def test_llm_failure_returns_502(client, mock_scoring_provider):
    mock_scoring_provider.score.side_effect = ScoringError(
        "LLM did not return a valid structured result after retry"
    )

    resp = await client.post(
        "/api/v1/analyze",
        data={
            "job_description": "Looking for a Python backend engineer.",
            "resume_text": "I have 3 years of Python experience.",
        },
    )

    assert resp.status_code == 502
    assert resp.json()["error"] == "llm_error"


async def test_cache_hit_skips_llm_call(client, mock_scoring_provider):
    mock_scoring_provider.score.return_value = VALID_ANALYSIS

    payload = {
        "job_description": "Looking for a Python backend engineer.",
        "resume_text": "I have 3 years of Python and FastAPI experience.",
    }

    first = await client.post("/api/v1/analyze", data=payload)
    assert first.status_code == 200
    assert first.json()["cached"] is False
    mock_scoring_provider.score.assert_called_once()

    second = await client.post("/api/v1/analyze", data=payload)
    assert second.status_code == 200
    assert second.json()["cached"] is True
    mock_scoring_provider.score.assert_called_once()


async def test_get_analysis_by_id(client, mock_scoring_provider):
    mock_scoring_provider.score.return_value = VALID_ANALYSIS

    created = await client.post(
        "/api/v1/analyze",
        data={
            "job_description": "Looking for a Python backend engineer.",
            "resume_text": "I have 3 years of Python and FastAPI experience.",
        },
    )
    analysis_id = created.json()["id"]

    resp = await client.get(f"/api/v1/analyze/{analysis_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == analysis_id


async def test_get_analysis_not_found_returns_404(client):
    resp = await client.get("/api/v1/analyze/doesnotexist")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


async def test_health_check(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_analyze_rate_limit_returns_429(client, mock_scoring_provider):
    mock_scoring_provider.score.return_value = VALID_ANALYSIS
    payload = {
        "job_description": "Looking for a Python backend engineer.",
        "resume_text": "I have 3 years of Python and FastAPI experience.",
    }

    for _ in range(10):
        resp = await client.post("/api/v1/analyze", data=payload)
        assert resp.status_code == 200

    resp = await client.post("/api/v1/analyze", data=payload)
    assert resp.status_code == 429
    assert resp.json()["error"] == "rate_limited"


async def test_list_analyses_returns_newest_first(client, mock_scoring_provider):
    mock_scoring_provider.score.return_value = VALID_ANALYSIS

    first = await client.post(
        "/api/v1/analyze",
        data={
            "job_description": "Looking for a Python backend engineer.",
            "resume_text": "resume one",
        },
    )
    second = await client.post(
        "/api/v1/analyze",
        data={
            "job_description": "Looking for a Python backend engineer.",
            "resume_text": "resume two",
        },
    )

    resp = await client.get("/api/v1/analyze")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert [item["id"] for item in body["items"]] == [
        second.json()["id"],
        first.json()["id"],
    ]


async def test_list_analyses_pagination(client, mock_scoring_provider):
    mock_scoring_provider.score.return_value = VALID_ANALYSIS

    for i in range(3):
        await client.post(
            "/api/v1/analyze",
            data={
                "job_description": "Looking for a Python backend engineer.",
                "resume_text": f"resume {i}",
            },
        )

    resp = await client.get("/api/v1/analyze", params={"limit": 1, "offset": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["limit"] == 1
    assert body["offset"] == 1
    assert len(body["items"]) == 1


async def test_list_analyses_empty(client):
    resp = await client.get("/api/v1/analyze")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"items": [], "total": 0, "limit": 20, "offset": 0}
