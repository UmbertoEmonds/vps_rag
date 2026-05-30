import re
from unittest.mock import AsyncMock, MagicMock, patch

from rag.config.settings import Settings
from rag.rag.ingestion.web_loader import load_url


def test_default_web_max_pages():
    with patch.dict("os.environ", {
        "MISTRAL_API_KEY": "x",
        "POSTGRES_PASSWORD": "x",
    }):
        s = Settings()
        assert s.web_max_pages == 100


def test_web_max_pages_override():
    with patch.dict("os.environ", {
        "MISTRAL_API_KEY": "x",
        "POSTGRES_PASSWORD": "x",
        "WEB_MAX_PAGES": "50",
    }):
        s = Settings()
        assert s.web_max_pages == 50


def _make_fake_docs(urls_and_texts: list[tuple[str, str]]):
    """Build fake LangChain Document objects."""
    docs = []
    for url, text in urls_and_texts:
        doc = MagicMock()
        doc.page_content = text
        doc.metadata = {"source": url}
        docs.append(doc)
    return docs


def test_load_url_returns_texts_and_metadata():
    fake_docs = _make_fake_docs([
        ("https://example.com", "Hello world"),
        ("https://example.com/about", "About page"),
    ])
    with patch(
        "rag.rag.ingestion.web_loader.RecursiveUrlLoader"
    ) as MockLoader:
        MockLoader.return_value.load.return_value = fake_docs
        texts, metadata = load_url("https://example.com", max_pages=10)

    assert texts == ["Hello world", "About page"]
    assert metadata["source"] == "https://example.com"
    assert metadata["pages_crawled"] == 2


def test_load_url_respects_max_pages():
    fake_docs = _make_fake_docs([
        ("https://example.com", f"Page {i}") for i in range(20)
    ])
    with patch(
        "rag.rag.ingestion.web_loader.RecursiveUrlLoader"
    ) as MockLoader:
        MockLoader.return_value.load.return_value = fake_docs
        texts, metadata = load_url("https://example.com", max_pages=5)

    assert len(texts) == 5
    assert metadata["pages_crawled"] == 5


def test_load_url_passes_correct_params_to_loader():
    with patch(
        "rag.rag.ingestion.web_loader.RecursiveUrlLoader"
    ) as MockLoader:
        MockLoader.return_value.load.return_value = []
        load_url("https://example.com/path", max_pages=42)

    call_kwargs = MockLoader.call_args.kwargs
    assert call_kwargs["url"] == "https://example.com/path"
    assert call_kwargs["max_depth"] == 10
    link_regex_arg = call_kwargs.get("link_regex")
    assert isinstance(link_regex_arg, re.Pattern)
    assert "example" in link_regex_arg.pattern
    assert "com" in link_regex_arg.pattern
