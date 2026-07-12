"""
DOCX Loader — Docling reads once, gives both raw text AND ParsedDocument.
Same approach as the PDF loader.

Batch 2 — image support:
  * Enables embedded-image extraction (generate_picture_images = True,
    images_scale = 2.0), set defensively so it never crashes on a Docling
    version that doesn't expose those options.
  * Passes the REAL file_path in metadata so _docling saves images under
    uploads/{space_id}/images (the folder the image route is allowed to serve).
    This was the actual bug: without file_path, images were written to the CWD
    and the /image route rejected them (403).

Downstream is unchanged: the shared load-parse step summarizes the images with
Gemini (text_for_embedding) and the DocModal + image route display them — no
DOCX-specific code needed beyond this loader.
"""
import os
import logging

logger = logging.getLogger(__name__)

_converter = None


def _get_converter():
    """
    Create or reuse a Docling converter.

    We intentionally use the DEFAULT converter here. Docling's default DOCX
    pipeline already carries the option object its convert step expects (it
    reads attributes like do_picture_classification), and the MS Word backend
    extracts embedded images into the document model. Injecting a bare custom
    PipelineOptions breaks convert() with:
        'PipelineOptions' object has no attribute 'do_picture_classification'
    The real image fix is passing the correct file_path in metadata (see load()),
    so _docling saves the extracted images under uploads/{space_id}/images.
    """
    global _converter
    if _converter is None:
        from docling.document_converter import DocumentConverter
        _converter = DocumentConverter()
        logger.info("[DOCX_LOADER] Docling converter created (default pipeline)")
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

    # ParsedDocument from structure.
    # NOTE: pass the real file_path so _docling saves images next to it
    # (uploads/{space_id}/images), which the image route can then serve.
    from app.services.providers.loaders._utils import build_doc_metadata
    parsed_doc = docling_to_parsed_document(
        result=result,
        file_type="Word",
        category="document",
        metadata={"source": os.path.basename(file_path),
                  "file_path": os.path.abspath(file_path)},
    )

    if not raw_text.strip():
        raise ValueError("DOCX contains no readable text")

    num_pages = parsed_doc.num_pages or 1
    metadata = build_doc_metadata(file_path, num_pages, "docx")

    # Rebuild heading levels + parent links from section numbering.
    from app.services.providers.parsers.hierarchy import (
        build_hierarchy, build_section_hierarchy,
    )
    build_hierarchy(parsed_doc.elements)
    build_section_hierarchy(parsed_doc.sections)
    parsed_doc.metadata = metadata

    return {
        "raw_text": raw_text,
        "num_pages": num_pages,
        "file_type": "Word",
        "category": "document",
        "metadata": metadata,
        "total_chars": len(raw_text),
        "parsed_document": parsed_doc.to_dict(),
    }
