import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_documents_empty(async_client: AsyncClient):
    response = await async_client.get("/api/v1/documents")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_ingest_rejects_non_pdf(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/documents/ingest",
        files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_unknown_document(async_client: AsyncClient):
    import uuid
    fake_id = str(uuid.uuid4())
    response = await async_client.delete(f"/api/v1/documents/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_ingest_urls_returns_results(async_client: AsyncClient):
    with patch(
        "rag.api.routers.ingestion.ingest_url",
        new=AsyncMock(return_value=MagicMock(
            document_id="00000000-0000-0000-0000-000000000001",
            filename="https://example.com",
            chunks_created=3,
            already_existed=False,
        )),
    ):
        response = await async_client.post(
            "/api/v1/documents/ingest-urls",
            json={"urls": ["https://example.com"]},
        )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["filename"] == "https://example.com"
    assert data[0]["chunks_created"] == 3
    assert data[0]["error"] is None


@pytest.mark.asyncio
async def test_ingest_urls_empty_list_returns_empty(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/documents/ingest-urls",
        json={"urls": []},
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_ingest_urls_invalid_url_returns_422(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/documents/ingest-urls",
        json={"urls": ["not-a-url"]},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ingest_urls_passes_max_pages(async_client: AsyncClient):
    mock_ingest = AsyncMock(return_value=MagicMock(
        document_id="00000000-0000-0000-0000-000000000001",
        filename="https://example.com",
        chunks_created=3,
        already_existed=False,
    ))
    with patch("rag.api.routers.ingestion.ingest_url", new=mock_ingest):
        response = await async_client.post(
            "/api/v1/documents/ingest-urls",
            json={"urls": ["https://example.com"], "max_pages": 42},
        )
    assert response.status_code == 200
    data = response.json()
    assert data[0]["error"] is None
    mock_ingest.assert_called_once()
    _, kwargs = mock_ingest.call_args
    assert kwargs.get("max_pages") == 42


@pytest.mark.asyncio
async def test_ingest_urls_rejects_zero_max_pages(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/documents/ingest-urls",
        json={"urls": ["https://example.com"], "max_pages": 0},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ingest_urls_rejects_negative_max_pages(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/documents/ingest-urls",
        json={"urls": ["https://example.com"], "max_pages": -1},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ingest_urls_isolates_per_url_errors(async_client: AsyncClient):
    async def fake_ingest(url, db, max_pages=None):
        if "bad" in url:
            raise ValueError("No text extracted from URL")
        return MagicMock(
            document_id="00000000-0000-0000-0000-000000000001",
            filename=url,
            chunks_created=2,
            already_existed=False,
        )

    with patch("rag.api.routers.ingestion.ingest_url", side_effect=fake_ingest):
        response = await async_client.post(
            "/api/v1/documents/ingest-urls",
            json={"urls": ["https://example.com", "https://bad.example.com"]},
        )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["error"] is None
    assert data[0]["chunks_created"] == 2
    assert data[1]["error"] is not None
    assert data[1]["chunks_created"] == 0
