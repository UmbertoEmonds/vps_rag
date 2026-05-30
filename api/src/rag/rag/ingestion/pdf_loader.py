from pathlib import Path

from pypdf import PdfReader


def load_pdf(file_path: str | Path) -> tuple[list[str], dict]:
    """Load a PDF file and return page texts and metadata.

    Returns:
        A tuple of (pages, metadata) where pages is a list of text strings
        (one per page) and metadata is a dict of PDF document info.
    """
    reader = PdfReader(str(file_path))
    pages = [page.extract_text() or "" for page in reader.pages]
    metadata = {k: str(v) for k, v in (reader.metadata or {}).items()}
    metadata["page_count"] = len(pages)
    return pages, metadata
