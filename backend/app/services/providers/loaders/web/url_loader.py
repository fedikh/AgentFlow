"""
URL Loader — scrapes a web page using requests + BeautifulSoup.

Returns raw text content stripped of scripts, styles, nav elements.
"""
import logging

logger = logging.getLogger(__name__)


def load(url: str) -> dict:
    logger.info(f"[URL_LOADER] Loading: {url}")

    import requests
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        raise ValueError(f"Failed to fetch URL '{url}': {str(e)}")

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove non-content
    for tag in soup(["script", "style", "nav", "footer", "aside", "iframe", "header"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    if not text.strip():
        raise ValueError(f"No content found at {url}")

    # Extract title
    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    return {
        "raw_text": text,
        "num_pages": 1,
        "file_type": "HTML",
        "category": "web",
        "metadata": {"source_url": url, "title": title},
        "total_chars": len(text),
    }
