"""
JSON Loader — validates the file and produces a pretty-printed text preview.

Structural (tree) parsing into the element schema happens in the Parse step
(json_parser), so the lifecycle stays UPLOAD → LOADED → (Parse) → EXTRACTED and
the manual "Parse" button is preserved.
"""
import os
import json
import logging

logger = logging.getLogger(__name__)


def load(file_path: str) -> dict:
    logger.info(f"[JSON_LOADER] Loading: {os.path.basename(file_path)}")

    from app.services.providers.loaders._utils import (
        read_text_file, clean_text, build_doc_metadata,
    )

    raw = read_text_file(file_path)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON file: {e}")

    raw_text = clean_text(json.dumps(data, indent=2, ensure_ascii=False))
    metadata = build_doc_metadata(file_path, 1, "json", parser_name="python-json")

    return {
        "raw_text": raw_text,
        "num_pages": 1,
        "file_type": "JSON",
        "category": "document",
        "metadata": metadata,
        "total_chars": len(raw_text),
    }
