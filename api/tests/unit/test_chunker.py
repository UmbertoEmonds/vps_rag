from unittest.mock import patch

from rag.rag.ingestion.chunker import chunk_texts


def test_chunk_texts_basic():
    pages = ["word " * 200]
    with patch("rag.rag.ingestion.chunker.get_settings") as mock_settings:
        mock_settings.return_value.chunk_size = 100
        mock_settings.return_value.chunk_overlap = 10
        chunks = chunk_texts(pages)

    assert len(chunks) > 1
    for chunk in chunks:
        assert "content" in chunk
        assert "chunk_index" in chunk
        assert len(chunk["content"]) <= 200  # some tolerance for splitter


def test_chunk_texts_empty_pages():
    with patch("rag.rag.ingestion.chunker.get_settings") as mock_settings:
        mock_settings.return_value.chunk_size = 512
        mock_settings.return_value.chunk_overlap = 64
        chunks = chunk_texts(["", "   "])

    assert chunks == []


def test_chunk_texts_propagates_metadata():
    pages = ["Hello world. " * 50]
    meta = {"filename": "test.pdf"}
    with patch("rag.rag.ingestion.chunker.get_settings") as mock_settings:
        mock_settings.return_value.chunk_size = 100
        mock_settings.return_value.chunk_overlap = 10
        chunks = chunk_texts(pages, source_metadata=meta)

    for chunk in chunks:
        assert chunk["metadata"]["filename"] == "test.pdf"
