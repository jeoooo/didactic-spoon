from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class AnalysisResult(BaseModel):
    """Structured resume-vs-JD match analysis.

    This is the shape both the API response and the LLM's structured
    output conform to, so validating the LLM's JSON against this model
    is what gives us confidence in the output.
    """

    id: str
    match_score: int = Field(ge=0, le=100)
    summary: str
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    cached: bool = False
    created_at: datetime

    @field_validator("match_score", mode="before")
    @classmethod
    def clamp_score(cls, v: int) -> int:
        return max(0, min(100, int(v)))


class LLMAnalysis(BaseModel):
    """The subset of AnalysisResult the LLM is asked to produce."""

    match_score: int = Field(ge=0, le=100)
    summary: str
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)

    @field_validator("match_score", mode="before")
    @classmethod
    def clamp_score(cls, v: int) -> int:
        return max(0, min(100, int(v)))


class AnalysisListResponse(BaseModel):
    """Paginated list of past analyses, newest first."""

    items: list[AnalysisResult]
    total: int
    limit: int
    offset: int


class ErrorResponse(BaseModel):
    error: str
    detail: str
