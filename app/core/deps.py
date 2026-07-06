from functools import lru_cache

from app.core.scoring import OpenCodeScoringProvider, ScoringProvider


@lru_cache
def get_scoring_provider() -> ScoringProvider:
    return OpenCodeScoringProvider()
