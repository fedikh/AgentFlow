"""
JSON Parser — builds the tree element schema (object / array / key_value).
Uses Python's stdlib `json`. See parsers.tree_elements.build_json_elements.
"""
import os
import json
import logging
from app.services.providers.parsers.parsed_document import ParsedDocument, Section

logger = logging.getLogger(__name__)


def parse(loaded_data: dict) -> ParsedDocument:
    fp = loaded_data.get("file_path")
    if fp and os.path.exists(fp):
        with open(fp, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
    else:
        raw = loaded_data.get("raw_text", "")
        if not raw.strip():
            raise ValueError("No JSON data to parse")
        data = json.loads(raw)

    logger.info("[JSON_PARSER] Building tree elements")

    meta = dict(loaded_data.get("metadata", {}))
    from app.services.providers.parsers.tree_elements import build_json_elements
    elements, root_type, schema_detected, text_repr = build_json_elements(
        data, source=meta.get("source"))

    meta.update({"root": root_type, "schema_detected": schema_detected,
                 "encoding": "utf-8", "source_type": "json"})

    # One section holds the flattened semantic text for chunking/embedding.
    sections = [Section(heading="", content=text_repr, level=1, page=1)]

    return ParsedDocument(
        title=meta.get("source", ""), sections=sections, elements=elements,
        metadata=meta, num_pages=1, file_type="JSON", category="structured_data",
    )
