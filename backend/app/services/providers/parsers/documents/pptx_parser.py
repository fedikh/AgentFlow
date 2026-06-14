"""
PPTX Parser — uses pre-parsed document from loader.
Fallback re-reads with python-pptx (not Docling).
"""
import logging
from app.services.providers.parsers.parsed_document import ParsedDocument

logger = logging.getLogger(__name__)


def parse(loaded_data: dict) -> ParsedDocument:
    if "parsed_document" in loaded_data and loaded_data["parsed_document"]:
        logger.info("[PPTX_PARSER] Using pre-parsed document from loader")
        return ParsedDocument.from_dict(loaded_data["parsed_document"])

    # Fallback: re-read with python-pptx
    file_path = loaded_data.get("file_path")
    if not file_path:
        raise ValueError("No file path and no pre-parsed document")

    logger.info(f"[PPTX_PARSER] Fallback: re-parsing with python-pptx")

    # Import the loader and use it
    from app.services.providers.loaders.documents.pptx_loader import load
    result = load(file_path)

    if "parsed_document" in result:
        return ParsedDocument.from_dict(result["parsed_document"])

    raise ValueError("Failed to parse PPTX")