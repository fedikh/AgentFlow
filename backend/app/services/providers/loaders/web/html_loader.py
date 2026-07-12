"""
HTML Loader — reads an uploaded .html file (encoding-aware) and PRESERVES the
raw HTML so the web parser can extract the canonical element model. raw_text is
a readable text preview.
"""
import os
import logging

logger = logging.getLogger(__name__)


def load(file_path: str) -> dict:
    logger.info(f"[HTML_LOADER] Loading: {os.path.basename(file_path)}")

    from bs4 import BeautifulSoup
    from app.services.providers.loaders._utils import read_text_file
    from app.services.providers.parsers.web_elements import extract_web_metadata

    html = read_text_file(file_path)
    soup = BeautifulSoup(html, "html.parser")
    meta = extract_web_metadata(soup, None)

    for tag in soup(["script", "style", "nav", "footer", "aside", "header", "iframe"]):
        tag.decompose()
    raw_text = soup.get_text("\n", strip=True)
    if not raw_text.strip():
        raise ValueError("HTML file contains no readable content")

    metadata = {"source": os.path.basename(file_path), "mime_type": "text/html"}
    metadata.update({k: v for k, v in meta.items() if v})

    return {
        "raw_text": raw_text,
        "num_pages": 1,
        "file_type": "HTML",
        "category": "web",
        "html": html,
        "metadata": metadata,
        "total_chars": len(raw_text),
    }
