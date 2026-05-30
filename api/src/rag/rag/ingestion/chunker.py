from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.config.settings import get_settings


def chunk_texts(pages: list[str], source_metadata: dict | None = None) -> list[dict]:
    """Split page texts into overlapping chunks.

    Returns:
        A list of dicts with keys: content, chunk_index, metadata.
    """
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
    )

    full_text = "\n\n".join(pages)
    raw_chunks = splitter.split_text(full_text)

    base_metadata = source_metadata or {}
    return [
        {"content": text, "chunk_index": i, "metadata": {**base_metadata, "chunk_index": i}}
        for i, text in enumerate(raw_chunks)
        if text.strip()
    ]
