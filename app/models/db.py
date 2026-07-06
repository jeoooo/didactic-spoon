from datetime import datetime

from sqlalchemy import Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


class Base(DeclarativeBase):
    pass


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (Index("ix_analyses_resume_jd_hash", "resume_hash", "jd_hash"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    resume_hash: Mapped[str] = mapped_column(String, nullable=False)
    jd_hash: Mapped[str] = mapped_column(String, nullable=False)
    match_score: Mapped[int] = mapped_column(nullable=False)
    result_json: Mapped[dict] = mapped_column(
        JSONB().with_variant(SQLiteJSON(), "sqlite"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )


engine = create_async_engine(settings.database_url)
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
