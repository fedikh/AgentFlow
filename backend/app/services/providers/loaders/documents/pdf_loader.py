"""
PDF Loader — Docling reads once, gives both raw text AND ParsedDocument.

Output:
  raw_text         → for "Loaded Text" tab
  parsed_document  → for "Parsed Blocks" tab (already structured)
  
No pdfplumber, no LlamaIndex. Just Docling.
"""
import os
import gc
import tempfile
import logging

logger = logging.getLogger(__name__)

BATCH_SIZE = 10
_converter = None  # reuse across calls


def _get_converter():
    """Create or reuse Docling converter."""
    global _converter
    if _converter is None:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        opts = PdfPipelineOptions()
        opts.generate_picture_images = False

        _converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=opts)
            }
        )
        logger.info("[PDF_LOADER] Docling converter created (reusable)")
    return _converter


def load(file_path: str) -> dict:
    logger.info(f"[PDF_LOADER] Loading with Docling: {os.path.basename(file_path)}")

    # Count pages first (fast, no ML)
    import fitz
    doc = fitz.open(file_path)
    num_pages = len(doc)
    doc.close()

    converter = _get_converter()

    if num_pages <= BATCH_SIZE:
        logger.info(f"[PDF_LOADER] {num_pages} pages → direct")
        return _load_single(converter, file_path, num_pages)
    else:
        logger.info(f"[PDF_LOADER] {num_pages} pages → batched ({BATCH_SIZE}/batch)")
        return _load_batched(converter, file_path, num_pages)


def _load_single(converter, file_path, num_pages):
    """Load a small PDF in one shot."""
    from app.services.providers.parsers._docling import docling_to_parsed_document

    result = converter.convert(file_path)

    # Raw text from Docling's markdown export
    raw_text = result.document.export_to_markdown()

    from app.services.providers.loaders._utils import clean_text
    raw_text = clean_text(raw_text)

    # ParsedDocument from Docling's structure
    metadata = {"source": os.path.basename(file_path), "parser": "docling"}
    parsed_doc = docling_to_parsed_document(
        result=result,
        file_type="PDF",
        category="document",
        metadata=metadata,
    )

    if not raw_text.strip():
        raise ValueError("PDF contains no readable text")

    return {
        "raw_text": raw_text,
        "num_pages": num_pages,
        "file_type": "PDF",
        "category": "document",
        "metadata": metadata,
        "total_chars": len(raw_text),
        "parsed_document": parsed_doc.to_dict(),  # ← structure ready
    }


def _load_batched(converter, file_path, num_pages):
    """Load a large PDF in batches."""
    import fitz
    from app.services.providers.parsers._docling import docling_to_parsed_document
    from app.services.providers.parsers.parsed_document import ParsedDocument

    all_raw_parts = []
    all_sections = []
    all_tables = []
    all_images = []
    title = ""
    failed_pages = []

    src = fitz.open(file_path)

    for start in range(0, num_pages, BATCH_SIZE):
        end = min(start + BATCH_SIZE, num_pages)
        logger.info(f"[PDF_LOADER] Batch: pages {start + 1}–{end}")

        tmp_path = None
        try:
            tmp = fitz.open()
            tmp.insert_pdf(src, from_page=start, to_page=end - 1)
            tmp_path = tempfile.mktemp(suffix=".pdf")
            tmp.save(tmp_path)
            tmp.close()

            result = converter.convert(tmp_path)

            # Raw text for this batch
            batch_text = result.document.export_to_markdown()
            if batch_text.strip():
                all_raw_parts.append(batch_text.strip())

            # Structure for this batch
            metadata = {"source": os.path.basename(file_path)}
            batch_doc = docling_to_parsed_document(
                result=result, file_type="PDF", category="document", metadata=metadata,
            )

            # Fix page numbers
            for sec in batch_doc.sections:
                sec.page += start
            for tab in batch_doc.tables:
                tab.page += start
            for img in batch_doc.images:
                img.page += start

            all_sections.extend(batch_doc.sections)
            all_tables.extend(batch_doc.tables)
            all_images.extend(batch_doc.images)

            if not title and batch_doc.title:
                title = batch_doc.title

        except Exception as e:
            logger.warning(f"[PDF_LOADER] Batch {start + 1}–{end} failed: {e}")
            failed_pages.extend(range(start + 1, end + 1))

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            gc.collect()

    src.close()

    raw_text = "\n\n".join(all_raw_parts)
    from app.services.providers.loaders._utils import clean_text
    raw_text = clean_text(raw_text)

    if not raw_text.strip() and not all_sections:
        raise ValueError("PDF contains no readable text")

    metadata = {
        "source": os.path.basename(file_path),
        "parser": "docling_batched",
        "batch_size": BATCH_SIZE,
    }
    if failed_pages:
        metadata["failed_pages"] = failed_pages

    parsed_doc = ParsedDocument(
        title=title,
        sections=all_sections,
        tables=all_tables,
        images=all_images,
        metadata=metadata,
        num_pages=num_pages,
        file_type="PDF",
        category="document",
        ocr_quality="good" if not failed_pages else "fair",
        ocr_issues=[f"Pages {failed_pages} failed"] if failed_pages else [],
    )

    logger.info(f"[PDF_LOADER] Done: {parsed_doc.total_sections} sections, {parsed_doc.total_tables} tables")

    return {
        "raw_text": raw_text,
        "num_pages": num_pages,
        "file_type": "PDF",
        "category": "document",
        "metadata": metadata,
        "total_chars": len(raw_text),
        "parsed_document": parsed_doc.to_dict(),  # ← structure ready
    }