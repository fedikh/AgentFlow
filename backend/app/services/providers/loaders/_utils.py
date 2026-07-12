"""
Shared utilities for all loaders.
"""
import re
import pathlib
from datetime import datetime, timezone
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


_MIME_BY_TYPE = {
    "pdf":  "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "txt":  "text/plain",
    "md":   "text/markdown",
    "json": "application/json",
    "xml":  "application/xml",
    "csv":  "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls":  "application/vnd.ms-excel",
}


def read_text_file(file_path: str) -> str:
    """Read a text/markdown file with encoding detection (robust to non-UTF-8)."""
    with open(file_path, "rb") as f:
        data = f.read()
    enc = "utf-8"
    try:
        import chardet
        enc = chardet.detect(data).get("encoding") or "utf-8"
    except Exception:
        pass
    return data.decode(enc, errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def _pkg_version(pkg: str) -> str:
    try:
        import importlib.metadata as _m
        return _m.version(pkg)
    except Exception:
        return "?"


# Map a parser name to the package whose version we report.
_PARSER_PKG = {
    "docling": "docling",
    "docling_batched": "docling",
    "python-pptx": "python-pptx",
    "pymupdf_fast": "pymupdf",
    "markdown-it-py": "markdown-it-py",
    "lxml": "lxml",
    "pandas": "pandas",
    "openpyxl": "openpyxl",
}

# Stdlib-based parsers → report the Python version.
_STDLIB_PARSERS = {"python-json"}


def _parser_version(parser_name: str) -> str:
    if parser_name in _PARSER_PKG:
        return _pkg_version(_PARSER_PKG[parser_name])
    if parser_name in _STDLIB_PARSERS:
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}"
    return "native"


def _sha256(file_path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_doc_metadata(file_path: str, num_pages: int, file_type: str,
                       parser_name: str = "docling", extra: dict = None) -> dict:
    """
    Document-level metadata for the element schema, shared by all doc loaders.
    Keeps `source`/`file_path` (image extraction derives its folder from them).
    """
    ft = (file_type or "").lower()
    meta = {
        "source": pathlib.Path(file_path).name,
        "file_path": str(pathlib.Path(file_path).resolve()),
        "file_type": ft,
        "mime_type": _MIME_BY_TYPE.get(ft, "application/octet-stream"),
        "parser": {"name": parser_name, "version": _parser_version(parser_name)},
        "page_count": num_pages,
        "checksum": "sha256:" + _sha256(file_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        meta.update(extra)
    return meta


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
