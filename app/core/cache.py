from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Analysis
from app.models.schemas import AnalysisResult


async def get_cached_result(
    session: AsyncSession, resume_hash: str, jd_hash: str
) -> AnalysisResult | None:
    stmt = (
        select(Analysis)
        .where(Analysis.resume_hash == resume_hash, Analysis.jd_hash == jd_hash)
        .order_by(Analysis.created_at.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None

    result = AnalysisResult.model_validate(row.result_json)
    result.cached = True
    return result
