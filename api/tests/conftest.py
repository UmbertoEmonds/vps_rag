from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from rag.api.app import create_app
from rag.db.base import Base
from rag.db.session import get_db
import rag.db.models.document  # noqa: F401 — register models
import rag.db.models.conversation  # noqa: F401

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    execution_options={"schema_translate_map": {"rag": None}},
)
test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture
async def setup_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(setup_test_db) -> AsyncGenerator[AsyncSession, None]:
    async with test_session_factory() as session:
        yield session


@pytest.fixture
def mock_embeddings():
    """Return fixed-dimension zero vectors instead of calling Mistral."""
    dummy = [[0.0] * 1024]
    with patch("rag.rag.embeddings.mistral_embeddings.embed_documents", new=AsyncMock(return_value=dummy)), \
         patch("rag.rag.embeddings.mistral_embeddings.embed_query", new=AsyncMock(return_value=[0.0] * 1024)):
        yield


@pytest.fixture
async def async_client(db_session: AsyncSession):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
