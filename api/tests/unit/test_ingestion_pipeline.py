import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag.rag.ingestion.pipeline import _compute_hash, ingest_pdf, _hash_url, ingest_url


def test_compute_hash_is_deterministic(tmp_path: Path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"fake pdf content")
    h1 = _compute_hash(pdf)
    h2 = _compute_hash(pdf)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_compute_hash_differs_for_different_content(tmp_path: Path):
    pdf1 = tmp_path / "a.pdf"
    pdf2 = tmp_path / "b.pdf"
    pdf1.write_bytes(b"content A")
    pdf2.write_bytes(b"content B")
    assert _compute_hash(pdf1) != _compute_hash(pdf2)


@pytest.mark.asyncio
async def test_ingest_pdf_idempotent(tmp_path: Path, mock_embeddings):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"fake pdf")

    mock_doc = MagicMock()
    mock_doc.id = "existing-id"
    mock_doc.filename = "doc.pdf"

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.add_all = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_doc
    mock_db.execute.return_value = mock_result

    with patch("rag.rag.ingestion.pipeline.load_pdf", return_value=(["page text"], {})):
        result = await ingest_pdf(pdf, mock_db)

    assert result.already_existed is True
    assert result.chunks_created == 0


def test_hash_url_is_deterministic():
    h1 = _hash_url("https://example.com")
    h2 = _hash_url("https://example.com")
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_hash_url_differs_for_different_urls():
    assert _hash_url("https://example.com") != _hash_url("https://other.com")


def test_hash_url_normalizes_trailing_slash():
    assert _hash_url("https://example.com") == _hash_url("https://example.com/")


@pytest.mark.asyncio
async def test_ingest_url_idempotent(mock_embeddings):
    mock_doc = MagicMock()
    mock_doc.id = "existing-id"
    mock_doc.filename = "https://example.com"

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.add_all = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_doc
    mock_db.execute.return_value = mock_result

    with patch("rag.rag.ingestion.pipeline.load_url", return_value=(["text"], {"source": "https://example.com", "pages_crawled": 1})):
        result = await ingest_url("https://example.com", mock_db)

    assert result.already_existed is True
    assert result.chunks_created == 0


@pytest.mark.asyncio
async def test_ingest_url_new_document(mock_embeddings):
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.add_all = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    with patch("rag.rag.ingestion.pipeline.load_url", return_value=(["page text"], {"source": "https://example.com", "pages_crawled": 1})):
        result = await ingest_url("https://example.com", mock_db)

    assert result.already_existed is False
    assert result.chunks_created >= 1
