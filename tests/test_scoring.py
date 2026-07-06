from unittest.mock import MagicMock, patch

import pytest

from app.core.scoring import OpenCodeScoringProvider, ScoringError

VALID_JSON = """{
  "match_score": 78,
  "summary": "Strong backend fit.",
  "matched_skills": ["Python", "FastAPI"],
  "missing_skills": ["Kubernetes"],
  "strengths": ["3 years experience"],
  "gaps": ["No cloud experience"]
}"""


def _mock_response(content: str) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=content))]
    return resp


@patch("app.core.scoring.OpenAI")
def test_score_parses_clean_json(mock_openai_cls):
    mock_client = mock_openai_cls.return_value
    mock_client.chat.completions.create.return_value = _mock_response(VALID_JSON)

    provider = OpenCodeScoringProvider()
    result = provider.score("resume text", "job description")

    assert result.match_score == 78
    assert result.matched_skills == ["Python", "FastAPI"]
    mock_client.chat.completions.create.assert_called_once()


@patch("app.core.scoring.OpenAI")
def test_score_strips_markdown_fences(mock_openai_cls):
    fenced = f"```json\n{VALID_JSON}\n```"
    mock_client = mock_openai_cls.return_value
    mock_client.chat.completions.create.return_value = _mock_response(fenced)

    provider = OpenCodeScoringProvider()
    result = provider.score("resume text", "job description")

    assert result.match_score == 78


@patch("app.core.scoring.OpenAI")
def test_score_strips_stray_prose(mock_openai_cls):
    noisy = f"Sure, here's the analysis:\n{VALID_JSON}\nLet me know if you need more."
    mock_client = mock_openai_cls.return_value
    mock_client.chat.completions.create.return_value = _mock_response(noisy)

    provider = OpenCodeScoringProvider()
    result = provider.score("resume text", "job description")

    assert result.match_score == 78


@patch("app.core.scoring.OpenAI")
def test_score_retries_once_on_malformed_json(mock_openai_cls):
    mock_client = mock_openai_cls.return_value
    mock_client.chat.completions.create.side_effect = [
        _mock_response("not json at all"),
        _mock_response(VALID_JSON),
    ]

    provider = OpenCodeScoringProvider()
    result = provider.score("resume text", "job description")

    assert result.match_score == 78
    assert mock_client.chat.completions.create.call_count == 2


@patch("app.core.scoring.OpenAI")
def test_score_raises_scoring_error_after_failed_retry(mock_openai_cls):
    mock_client = mock_openai_cls.return_value
    mock_client.chat.completions.create.side_effect = [
        _mock_response("not json"),
        _mock_response("still not json"),
    ]

    provider = OpenCodeScoringProvider()
    with pytest.raises(ScoringError):
        provider.score("resume text", "job description")

    assert mock_client.chat.completions.create.call_count == 2


@patch("app.core.scoring.OpenAI")
def test_score_clamps_out_of_range_match_score(mock_openai_cls):
    bad_score = VALID_JSON.replace('"match_score": 78', '"match_score": 150')
    mock_client = mock_openai_cls.return_value
    mock_client.chat.completions.create.return_value = _mock_response(bad_score)

    provider = OpenCodeScoringProvider()
    result = provider.score("resume text", "job description")

    assert result.match_score == 100
