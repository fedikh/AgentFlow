"""
HTML Loader — uses BeautifulSoup + chardet for encoding detection.

Removes non-content elements (script, style, nav, footer, aside).
Extracts tables separately as markdown.
"""
import os
import logging

logger = logging.getLogger(__name__)


def load(file_path: str) -> dict:
    logger.info(f"[HTML_LOADER] Loading: {os.path.basename(file_path)}")

    from bs4 import BeautifulSoup
    import chardet

    with open(file_path, "rb") as f:
        raw = f.read()
    detected = chardet.detect(raw)
    encoding = detected.get("encoding", "utf-8") or "utf-8"
    html = raw.decode(encoding, errors="replace")

    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content elements
    for tag in soup(["script", "style", "nav", "footer", "aside", "iframe", "header"]):
        tag.decompose()

    # Extract tables → markdown format
    tables_text = []
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            rows.append(" | ".join(cells))
        if rows:
            tables_text.append("\n".join(rows))
        table.decompose()

    # Remaining text content
    text = soup.get_text(separator="\n", strip=True)
    full_text = text
    if tables_text:
        full_text += "\n\n" + "\n\n".join(tables_text)

    if not full_text.strip():
        raise ValueError("HTML file contains no readable content")

    # Try to extract title
    title = ""
    title_tag = BeautifulSoup(html, "html.parser").find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    return {
        "raw_text": full_text,
        "num_pages": 1,
        "file_type": "HTML",
        "category": "web",
        "metadata": {"source": file_path, "title": title, "encoding": encoding},
        "total_chars": len(full_text),
    }
