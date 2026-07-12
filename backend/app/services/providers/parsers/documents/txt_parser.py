"""
TXT Parser — heuristic structural parse into the element schema.
Shares its logic with the TXT loader via text_elements.build_plaintext.
"""
import logging
from app.services.providers.parsers.parsed_document import ParsedDocument

logger = logging.getLogger(__name__)


def parse(loaded_data: dict) -> ParsedDocument:
    raw_text = loaded_data.get("raw_text", "")
    if not raw_text.strip():
        raise ValueError("No text to parse")

    logger.info(f"[TXT_PARSER] Parsing {len(raw_text)} chars")

    from app.services.providers.parsers.text_elements import build_plaintext
    from app.services.providers.parsers.hierarchy import (
        build_hierarchy, build_section_hierarchy,
    )

    elements, sections = build_plaintext(raw_text)
    title = next((e["content"]["text"] for e in elements if e["type"] == "heading"), "")

    parsed = ParsedDocument(
        title=title, sections=sections, elements=elements,
        metadata=loaded_data.get("metadata", {}),
        file_type="Text", category="document",
    )
    build_hierarchy(parsed.elements)
    build_section_hierarchy(parsed.sections)
    return parsed
