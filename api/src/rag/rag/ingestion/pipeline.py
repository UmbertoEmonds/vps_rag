import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag.config.settings import get_settings
from rag.db.models.document import Document, DocumentChunk
from rag.rag.embeddings import mistral_embeddings
from rag.rag.ingestion.chunker import chunk_texts
from rag.rag.ingestion.pdf_loader import load_pdf
from rag.rag.ingestion.web_loader import load_url


@dataclass
class IngestionResult:
    document_id: uuid.UUID
    filename: str
    chunks_created: int
    already_existed: bool


def _compute_hash(file_path: str | Path) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            sha256.update(block)
    return sha256.hexdigest()


def _hash_url(url: str) -> str:
    """Return a SHA-256 hash of a normalized URL for deduplication."""
    normalized = url.rstrip("/").lower()
    return hashlib.sha256(normalized.encode()).hexdigest()


async def ingest_url(url: str, db: AsyncSession, max_pages: int | None = None) -> IngestionResult:
    """Ingest a web URL recursively into the vector store.

    Idempotent: re-ingesting the same URL (same normalized URL hash) is a no-op.
    """
    settings = get_settings()
    effective_max_pages = max_pages if max_pages is not None else settings.web_max_pages
    url_hash = _hash_url(url)

    # Check for existing document with same URL hash
    result = await db.execute(select(Document).where(Document.file_hash == url_hash))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return IngestionResult(
            document_id=existing.id,
            filename=existing.filename,
            chunks_created=0,
            already_existed=True,
        )

    # Crawl + chunk
    pages, web_metadata = load_url(url, max_pages=effective_max_pages)
    chunks = chunk_texts(pages, source_metadata=web_metadata)

    if not chunks:
        raise ValueError(f"No text extracted from URL: {url}")

    # Persist document first to get its ID
    document = Document(filename=url, file_hash=url_hash, metadata_=web_metadata)
    db.add(document)
    await db.flush()

    # Embed all chunks in one batch call
    texts = [c["content"] for c in chunks]
    embeddings = await mistral_embeddings.embed_documents(texts)

    db_chunks = [
        DocumentChunk(
            document_id=document.id,
            content=chunk["content"],
            embedding=embedding,
            chunk_index=chunk["chunk_index"],
            metadata_=chunk["metadata"],
        )
        for chunk, embedding in zip(chunks, embeddings)
    ]
    db.add_all(db_chunks)
    await db.commit()

    return IngestionResult(
        document_id=document.id,
        filename=url,
        chunks_created=len(db_chunks),
        already_existed=False,
    )


async def ingest_pdf(file_path: str | Path, db: AsyncSession) -> IngestionResult:
    """Ingest a PDF file into the vector store.

    Idempotent: re-ingesting the same file (same SHA-256) is a no-op.
    """
    file_path = Path(file_path)
    filename = file_path.name
    file_hash = _compute_hash(file_path)

    # Check for existing document with same hash
    result = await db.execute(select(Document).where(Document.file_hash == file_hash))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return IngestionResult(
            document_id=existing.id,
            filename=existing.filename,
            chunks_created=0,
            already_existed=True,
        )

    # Load + chunk
    pages, pdf_metadata = load_pdf(file_path)
    chunks = chunk_texts(pages, source_metadata={"filename": filename, **pdf_metadata})

    if not chunks:
        raise ValueError(f"No text extracted from PDF: {filename}")

    # Persist document first to get its ID
    document = Document(filename=filename, file_hash=file_hash, metadata_=pdf_metadata)
    db.add(document)
    await db.flush()  # get document.id without committing

    # Embed all chunks in one batch call
    texts = [c["content"] for c in chunks]
    embeddings = await mistral_embeddings.embed_documents(texts)

    db_chunks = [
        DocumentChunk(
            document_id=document.id,
            content=chunk["content"],
            embedding=embedding,
            chunk_index=chunk["chunk_index"],
            metadata_=chunk["metadata"],
        )
        for chunk, embedding in zip(chunks, embeddings)
    ]
    db.add_all(db_chunks)
    await db.commit()

    return IngestionResult(
        document_id=document.id,
        filename=filename,
        chunks_created=len(db_chunks),
        already_existed=False,
    )
