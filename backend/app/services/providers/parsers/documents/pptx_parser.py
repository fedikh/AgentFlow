"""
PPTX Parser — uses the ParsedDocument the loader already produced.
The loader runs during loading (python-pptx primary, Docling fallback), so no
need to read the file again.

If parsed_document exists in loaded_data → use it directly.
If not (legacy data) → fall back to re-running the loader.
"""
import logging
from app.services.providers.parsers.parsed_document import ParsedDocument

logger = logging.getLogger(__name__)


def parse(loaded_data: dict) -> ParsedDocument:
    if "parsed_document" in loaded_data and loaded_data["parsed_document"]:
        logger.info("[PPTX_PARSER] Using pre-parsed document from loader")
        return ParsedDocument.from_dict(loaded_data["parsed_document"])

    # Fallback: re-run the loader (python-pptx primary, Docling fallback).
    file_path = loaded_data.get("file_path")
    if not file_path:
        raise ValueError("No file path and no pre-parsed document")

    logger.info("[PPTX_PARSER] Fallback: re-parsing via loader")

    from app.services.providers.loaders.documents.pptx_loader import load
    result = load(file_path)
    if result.get("parsed_document"):
        return ParsedDocument.from_dict(result["parsed_document"])

    raise ValueError("Failed to parse PPTX")
