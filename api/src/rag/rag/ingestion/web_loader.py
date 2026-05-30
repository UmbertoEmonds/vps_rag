import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from langchain_community.document_loaders import RecursiveUrlLoader


def _extract_text(html: str) -> str:
    """Strip HTML tags and return plain text."""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n", strip=True)


def load_url(url: str, max_pages: int) -> tuple[list[str], dict]:
    """Crawl a URL recursively within its domain and return page texts and metadata.

    Stays within the same domain as the starting URL. Crawl depth is effectively
    unlimited (max_depth=10) but bounded by max_pages.

    Returns:
        A tuple of (texts, metadata) where texts is a list of plain-text strings
        (one per crawled page) and metadata is a dict describing the crawl.
    """
    domain = urlparse(url).netloc
    if not domain:
        raise ValueError(f"Could not extract domain from URL: {url!r}")
    link_regex = re.compile(rf"https?://{re.escape(domain)}")

    loader = RecursiveUrlLoader(
        url=url,
        max_depth=10,
        extractor=_extract_text,
        link_regex=link_regex,
    )
    docs = loader.load()
    docs = docs[:max_pages]

    texts = [doc.page_content for doc in docs]
    metadata = {
        "source": url,
        "type": "web",
        "domain": domain,
        "pages_crawled": len(docs),
    }
    return texts, metadata
