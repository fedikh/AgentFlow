"""
JSON Loader — reads JSON files, converts to readable text.
"""
import os
import json
import logging

logger = logging.getLogger(__name__)


def load(file_path: str) -> dict:
    logger.info(f"[JSON_LOADER] Loading: {os.path.basename(file_path)}")

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # Validate JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON file: {e}")

    # Pretty-print for raw text display
    raw_text = json.dumps(data, indent=2, ensure_ascii=False)

    # Metadata
    metadata = {
        "type": type(data).__name__,  # dict, list, etc.
        "source": os.path.basename(file_path),
    }

    if isinstance(data, dict):
        metadata["keys"] = ", ".join(list(data.keys())[:20])
        metadata["num_keys"] = len(data.keys())
    elif isinstance(data, list):
        metadata["num_items"] = len(data)
        if data and isinstance(data[0], dict):
            metadata["item_keys"] = ", ".join(list(data[0].keys())[:20])

    from app.services.providers.loaders._utils import clean_text
    raw_text = clean_text(raw_text)

    return {
        "raw_text": raw_text,
        "num_pages": 1,
        "file_type": "JSON",
        "category": "document",
        "metadata": metadata,
        "total_chars": len(raw_text),
    }