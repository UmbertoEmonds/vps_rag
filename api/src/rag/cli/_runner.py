from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from rag.config.settings import get_settings


@asynccontextmanager
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a short-lived async DB session for CLI use.

    Unlike db/session.py, this creates and disposes the engine lazily,
    with no module-level side effects.
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await engine.dispose()
