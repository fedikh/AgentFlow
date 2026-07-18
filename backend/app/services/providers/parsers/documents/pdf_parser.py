"""
PDF Parser — uses the ParsedDocument that the loader already produced.
Docling ran during loading, so no need to read the file again.

If parsed_document exists in loaded_data → use it directly.
If not (legacy data) → fall back to re-parsing with Docling (images ON).
"""
import logging
from app.services.providers.parsers.parsed_document import ParsedDocument

logger = logging.getLogger(__name__)


def parse(loaded_data: dict) -> ParsedDocument:
    # ── Check if loader already produced ParsedDocument ──
    if "parsed_document" in loaded_data and loaded_data["parsed_document"]:
        logger.info("[PDF_PARSER] Using pre-parsed document from loader (no re-read)")
        return ParsedDocument.from_dict(loaded_data["parsed_document"])

    # ── Fallback: re-parse with Docling (for legacy loaded_data) ──
    file_path = loaded_data.get("file_path")
    if not file_path:
        raise ValueError("No file path and no pre-parsed document")

    logger.info(f"[PDF_PARSER] Fallback: re-parsing with Docling: {file_path}")

    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from app.services.providers.parsers._docling import docling_to_parsed_document

    from app.config import settings
    opts = PdfPipelineOptions()
    opts.generate_picture_images = True   # ← match the loader
    # 2.0 renders 4× the pixels → std::bad_alloc (OOM) on CPU. Respect the
    # configured scale (default 1.0) like the loader does.
    try:
        opts.images_scale = float(settings.DOCLING_IMAGES_SCALE)
    except Exception:
        opts.images_scale = 1.0
    opts.do_ocr = False
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )
    result = converter.convert(file_path)

    metadata = dict(loaded_data.get("metadata", {}))
    metadata.setdefault("file_path", file_path)
    return docling_to_parsed_document(
        result=result,
        file_type="PDF",
        category="document",
        metadata=metadata,
    )