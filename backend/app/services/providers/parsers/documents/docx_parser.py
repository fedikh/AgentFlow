"""
DOCX Parser — uses the ParsedDocument that the loader already produced.
"""
import logging
from app.services.providers.parsers.parsed_document import ParsedDocument

logger = logging.getLogger(__name__)


def parse(loaded_data: dict) -> ParsedDocument:
    if "parsed_document" in loaded_data and loaded_data["parsed_document"]:
        logger.info("[DOCX_PARSER] Using pre-parsed document from loader")
        return ParsedDocument.from_dict(loaded_data["parsed_document"])

    # Fallback
    file_path = loaded_data.get("file_path")
    if not file_path:
        raise ValueError("No file path and no pre-parsed document")

    logger.info(f"[DOCX_PARSER] Fallback: re-parsing with Docling: {file_path}")

    from docling.document_converter import DocumentConverter
    from app.services.providers.parsers._docling import docling_to_parsed_document

    converter = DocumentConverter()
    result = converter.convert(file_path)

    return docling_to_parsed_document(
        result=result,
        file_type="Word",
        category="document",
        metadata=loaded_data.get("metadata", {}),
    )