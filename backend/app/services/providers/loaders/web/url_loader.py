"""
URL Loader — fetches a web page (Crawl4AI → requests fallback) and PRESERVES the
raw HTML so the web parser can extract the canonical element model. raw_text is
a readable markdown/text preview.
"""
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def load(url: str, render: bool = True) -> dict:
    logger.info(f"[URL_LOADER] Fetching: {url} (render={render})")

    from bs4 import BeautifulSoup
    from app.services.providers.loaders.web import web_fetch
    from app.services.providers.parsers.web_elements import extract_web_metadata

    # render → Crawl4AI (JS); otherwise fast requests (used for batch crawl).
    fetched = web_fetch.fetch_page(url) if render else web_fetch._fetch_requests(url)
    html = fetched["html"]
    soup = BeautifulSoup(html, "html.parser")
    meta = extract_web_metadata(soup, url)

    # Readable preview: Crawl4AI markdown, else stripped text.
    raw_text = (fetched.get("markdown") or "").strip()
    if not raw_text:
        for tag in soup(["script", "style", "nav", "footer", "aside", "header", "iframe"]):
            tag.decompose()
        raw_text = soup.get_text("\n", strip=True)
    if not raw_text.strip():
        raise ValueError(f"No readable content at {url}")

    metadata = {"source_url": url, "domain": urlparse(url).netloc,
                "engine": fetched["engine"], "mime_type": "text/html"}
    metadata.update({k: v for k, v in meta.items() if v})

    return {
        "raw_text": raw_text,
        "num_pages": 1,
        "file_type": "HTML",
        "category": "web",
        "html": html,            # ← raw HTML preserved for the parser
        "metadata": metadata,
        "total_chars": len(raw_text),
    }
