"""
Markdown Loader — reads the raw Markdown (encoding-aware).

Structural parsing into the element schema happens in the Parse step
(markdown_parser), so the lifecycle stays UPLOAD → LOADED → (Parse) → EXTRACTED
and the manual "Parse" button is preserved.
"""
import os
import logging

logger = logging.getLogger(__name__)


def load(file_path: str) -> dict:
    logger.info(f"[MD_LOADER] Loading: {os.path.basename(file_path)}")

    from app.services.providers.loaders._utils import (
        read_text_file, clean_text, build_doc_metadata,
    )

    raw = read_text_file(file_path)
    if not raw.strip():
        raise ValueError("Markdown file is empty")

    raw_text = clean_text(raw)
    metadata = build_doc_metadata(file_path, 1, "md", parser_name="markdown")

    return {
        "raw_text": raw_text,
        "num_pages": 1,
        "file_type": "Markdown",
        "category": "document",
        "metadata": metadata,
        "total_chars": len(raw_text),
    }
