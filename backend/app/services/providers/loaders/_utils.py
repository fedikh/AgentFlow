"""
Shared utilities for all loaders.
"""
import re
import pathlib
from datetime import datetime
from urllib.parse import urlparse


def clean_text(text: str) -> str:
    """
    Clean raw text from loader — fixes the 'too many empty lines' problem.

    What it does:
      - Strips trailing whitespace from each line
      - Collapses 3+ consecutive newlines into exactly 2 (one blank line)
      - Removes leading/trailing whitespace from the whole text
      - Removes NUL bytes and other control characters
    """
    if not text:
        return ""

    # Remove NUL bytes and control chars (except \n \r \t)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

    # Strip trailing whitespace from each line
    lines = [line.rstrip() for line in text.split("\n")]

    # Rejoin
    text = "\n".join(lines)

    # Collapse 3+ consecutive newlines into 2 (keeps paragraph breaks, removes excess)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def sanitize_metadata(metadata: dict) -> dict:
    """Make metadata JSON-serializable — handles pathlib.Path, datetime, etc."""
    clean = {}
    for k, v in metadata.items():
        if isinstance(v, (str, int, float, bool)):
            clean[k] = v
        elif v is None:
            clean[k] = None
        elif isinstance(v, pathlib.PurePath):
            clean[k] = str(v)
        elif isinstance(v, datetime):
            clean[k] = v.isoformat()
        else:
            try:
                clean[k] = str(v)
            except Exception:
                pass
    return clean


def validate_url(url: str) -> str:
    """Validate and clean URL."""
    if not url or not url.strip():
        raise ValueError("URL is empty")
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def get_url_filename(url: str) -> str:
    """Extract a filename from URL for storage."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if path:
        name = path.split("/")[-1]
        if name:
            return name
    return parsed.netloc.replace(".", "_") + ".html"
