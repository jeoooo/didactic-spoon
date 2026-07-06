from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_scoring_provider
from app.core.errors import NotFoundAppError, UpstreamAppError, ValidationAppError
from app.core.hashing import sha256
from app.core.ids import short_id
from app.core.pdf import PDFExtractionError, extract_text_from_pdf
from app.core.scoring import ScoringError, ScoringProvider
from app.models.db import Analysis, get_session
from app.models.schemas import AnalysisResult

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.post("/analyze", response_model=AnalysisResult)
async def analyze(
    job_description: str = Form(...),
    resume_file: UploadFile | None = File(None),
    resume_text: str | None = Form(None),
    scoring_provider: ScoringProvider = Depends(get_scoring_provider),
    session: AsyncSession = Depends(get_session),
) -> AnalysisResult:
    if not job_description or not job_description.strip():
        raise ValidationAppError("job_description is required")

    has_file = resume_file is not None and resume_file.filename
    has_text = resume_text is not None and resume_text.strip()

    if has_file and has_text:
        raise ValidationAppError(
            "Provide exactly one of resume_file or resume_text, not both"
        )
    if not has_file and not has_text:
        raise ValidationAppError("One of resume_file or resume_text is required")

    if has_file:
        data = await resume_file.read()
        try:
            resume_content = extract_text_from_pdf(data)
        except PDFExtractionError as exc:
            raise ValidationAppError(str(exc)) from exc
    else:
        resume_content = resume_text

    try:
        llm_result = scoring_provider.score(resume_content, job_description)
    except ScoringError as exc:
        raise UpstreamAppError(str(exc)) from exc

    result = AnalysisResult(
        id=short_id(),
        cached=False,
        created_at=datetime.now(timezone.utc),
        **llm_result.model_dump(),
    )

    row = Analysis(
        id=result.id,
        resume_hash=sha256(resume_content),
        jd_hash=sha256(job_description),
        match_score=result.match_score,
        result_json=result.model_dump(mode="json"),
    )
    session.add(row)
    await session.commit()

    return result


@router.get("/analyze/{analysis_id}", response_model=AnalysisResult)
async def get_analysis(
    analysis_id: str,
    session: AsyncSession = Depends(get_session),
) -> AnalysisResult:
    row = await session.get(Analysis, analysis_id)
    if row is None:
        raise NotFoundAppError(f"No analysis found with id '{analysis_id}'")

    return AnalysisResult.model_validate(row.result_json)
