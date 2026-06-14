"""
DOCX Loader — Docling reads once, gives both raw text AND ParsedDocument.
Same approach as PDF loader.
"""
import os
import logging

logger = logging.getLogger(__name__)

_converter = None


def _get_converter():
    global _converter
    if _converter is None:
        from docling.document_converter import DocumentConverter
        _converter = DocumentConverter()
        logger.info("[DOCX_LOADER] Docling converter created (reusable)")
    return _converter


def load(file_path: str) -> dict:
    logger.info(f"[DOCX_LOADER] Loading with Docling: {os.path.basename(file_path)}")

    from app.services.providers.parsers._docling import docling_to_parsed_document

    converter = _get_converter()
    result = converter.convert(file_path)

    # Raw text from markdown export
    raw_text = result.document.export_to_markdown()

    from app.services.providers.loaders._utils import clean_text
    raw_text = clean_text(raw_text)

    # ParsedDocument from structure
    metadata = {"source": os.path.basename(file_path), "parser": "docling"}
    parsed_doc = docling_to_parsed_document(
        result=result,
        file_type="Word",
        category="document",
        metadata=metadata,
    )

    if not raw_text.strip():
        raise ValueError("DOCX contains no readable text")

    return {
        "raw_text": raw_text,
        "num_pages": 1,
        "file_type": "Word",
        "category": "document",
        "metadata": metadata,
        "total_chars": len(raw_text),
        "parsed_document": parsed_doc.to_dict(),
    }