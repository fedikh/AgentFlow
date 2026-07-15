"""
PDF Loader — Docling reads once, gives both raw text AND ParsedDocument.

Output:
  raw_text         → for "Loaded Text" tab
  parsed_document  → for "Parsed Blocks" tab (already structured)

Images: generate_picture_images = True so PictureItems carry a PIL image
that _docling._save_image() can write to disk. OCR stays off (do_ocr=False)
because the vision LLM (Gemini) reads any text inside images at summary time.
"""
import os
import gc
import tempfile
import logging

logger = logging.getLogger(__name__)

BATCH_SIZE = 5
_converter = None  # reuse across calls


def _rich_metadata(file_path: str, num_pages: int, extra: dict = None) -> dict:
    """PDF document-level metadata for the element schema (shared builder)."""
    from app.services.providers.loaders._utils import build_doc_metadata
    parser = "docling_batched" if (extra and "batch_size" in extra) else "docling"
    return build_doc_metadata(file_path, num_pages, "pdf", parser_name=parser, extra=extra)


def _get_converter():
    """
    Create or reuse a Docling converter, tuned from settings.

    Key tuning (see app.config.Settings):
      * images_scale — 2.0 caused std::bad_alloc (OOM) on CPU and pages were
        silently skipped. Default is now 1.0 (reliable + faster, still fine for
        the vision LLM).
      * accelerator_options — device=AUTO so a GPU is used automatically if one
        is ever available; num_threads is capped to physical cores (over-
        subscribing logical cores makes CPU inference SLOWER).
      * table mode FAST — much quicker than ACCURATE, tables still extracted.

    Every option is set defensively so an older/newer Docling can't crash us.
    """
    global _converter
    if _converter is None:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from app.config import settings

        opts = PdfPipelineOptions()
        opts.generate_picture_images = True   # ← extract images to disk
        opts.do_ocr = False                   # vision LLM reads in-image text instead
        try:
            opts.images_scale = float(settings.DOCLING_IMAGES_SCALE)
        except Exception:
            opts.images_scale = 1.0

        # Table structure: keep it ON but use FAST mode by default.
        try:
            from docling.datamodel.pipeline_options import TableFormerMode
            opts.do_table_structure = True
            opts.table_structure_options.mode = (
                TableFormerMode.ACCURATE
                if str(settings.DOCLING_TABLE_MODE).lower() == "accurate"
                else TableFormerMode.FAST
            )
        except Exception as e:
            logger.warning(f"[PDF_LOADER] table mode not tunable: {e}")

        # Accelerator: auto-select device, don't oversubscribe CPU cores.
        try:
            from docling.datamodel.accelerator_options import (
                AcceleratorOptions, AcceleratorDevice,
            )
            opts.accelerator_options = AcceleratorOptions(
                num_threads=int(settings.DOCLING_NUM_THREADS),
                device=AcceleratorDevice.AUTO,
            )
        except Exception as e:
            logger.warning(f"[PDF_LOADER] accelerator not tunable: {e}")

        _converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=opts)
            }
        )
        logger.info(
            f"[PDF_LOADER] Docling converter created "
            f"(scale={opts.images_scale}, threads={settings.DOCLING_NUM_THREADS}, "
            f"table={settings.DOCLING_TABLE_MODE})"
        )
    return _converter


def load(file_path: str, extract_images: bool = True) -> dict:
    from app.config import settings

    # ── FAST path: PyMuPDF text extraction (no ML) — ~40× faster on CPU ──
    if str(getattr(settings, "PDF_EXTRACTION_MODE", "accurate")).lower() == "fast":
        logger.info(f"[PDF_LOADER] FAST mode (PyMuPDF): {os.path.basename(file_path)}")
        return _load_fast(file_path)

    logger.info(f"[PDF_LOADER] Loading with Docling: {os.path.basename(file_path)}"
                f"{'' if extract_images else ' (images OFF)'}")

    # Count pages first (fast, no ML)
    import fitz
    doc = fitz.open(file_path)
    num_pages = len(doc)
    doc.close()

    converter = _get_converter()

    if num_pages <= BATCH_SIZE:
        logger.info(f"[PDF_LOADER] {num_pages} pages → direct")
        return _load_single(converter, file_path, num_pages, extract_images)
    else:
        logger.info(f"[PDF_LOADER] {num_pages} pages → batched ({BATCH_SIZE}/batch)")
        return _load_batched(converter, file_path, num_pages, extract_images)


def _load_fast(file_path: str) -> dict:
    """
    Fast text-first extraction with PyMuPDF. One section per page, sorted in
    natural reading order. No ML layout/table/image models → near-instant, but
    tables become plain text and embedded images are not extracted.
    """
    import fitz
    from app.services.providers.parsers.parsed_document import ParsedDocument, Section

    doc = fitz.open(file_path)
    num_pages = len(doc)
    sections = []
    raw_parts = []

    for i, page in enumerate(doc):
        # sort=True → reading order (top-to-bottom, left-to-right by block)
        text = page.get_text("text", sort=True).strip()
        if not text:
            continue
        raw_parts.append(text)
        sections.append(Section(
            heading=f"Page {i + 1}",
            content=text,
            level=1,
            page=i + 1,
        ))
    doc.close()

    raw_text = "\n\n".join(raw_parts)
    from app.services.providers.loaders._utils import clean_text
    raw_text = clean_text(raw_text)

    if not raw_text.strip():
        raise ValueError("PDF contains no readable text (fast mode). "
                         "Try PDF_EXTRACTION_MODE=accurate for scanned files.")

    metadata = {
        "source": os.path.basename(file_path),
        "file_path": os.path.abspath(file_path),
        "parser": "pymupdf_fast",
    }
    parsed_doc = ParsedDocument(
        title=sections[0].content.split("\n")[0][:120] if sections else "",
        sections=sections,
        metadata=metadata,
        num_pages=num_pages,
        file_type="PDF",
        category="document",
    )
    logger.info(f"[PDF_LOADER] FAST done: {parsed_doc.total_sections} sections, "
                f"{len(raw_text)} chars")

    return {
        "raw_text": raw_text,
        "num_pages": num_pages,
        "file_type": "PDF",
        "category": "document",
        "metadata": metadata,
        "total_chars": len(raw_text),
        "parsed_document": parsed_doc.to_dict(),
    }


def _load_single(converter, file_path, num_pages, extract_images=True):
    """Load a small PDF in one shot."""
    from app.services.providers.parsers._docling import docling_to_parsed_document

    result = converter.convert(file_path)

    # Raw text from Docling's markdown export
    raw_text = result.document.export_to_markdown()

    from app.services.providers.loaders._utils import clean_text
    raw_text = clean_text(raw_text)

    # ParsedDocument from Docling's structure.
    # NOTE: pass the real file_path so _docling saves images next to it.
    metadata = _rich_metadata(file_path, num_pages)
    parsed_doc = docling_to_parsed_document(
        result=result,
        file_type="PDF",
        category="document",
        metadata=metadata,
        extract_images=extract_images,
    )

    if not raw_text.strip():
        raise ValueError("PDF contains no readable text")

    # Rebuild heading levels + parent links from section numbering.
    from app.services.providers.parsers.hierarchy import (
        build_hierarchy, build_section_hierarchy,
    )
    build_hierarchy(parsed_doc.elements)
    build_section_hierarchy(parsed_doc.sections)

    return {
        "raw_text": raw_text,
        "num_pages": num_pages,
        "file_type": "PDF",
        "category": "document",
        "metadata": metadata,
        "total_chars": len(raw_text),
        "parsed_document": parsed_doc.to_dict(),  # ← structure ready
    }


def _load_batched(converter, file_path, num_pages, extract_images=True):
    """Load a large PDF in batches."""
    import fitz
    from app.services.providers.parsers._docling import docling_to_parsed_document
    from app.services.providers.parsers.parsed_document import ParsedDocument

    all_raw_parts = []
    all_sections = []
    all_tables = []
    all_images = []
    all_elements = []
    ro_start = 0
    heading_stack = []   # carried across batches → parent resolution survives
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

            # Structure for this batch — pass real file_path so images save
            # under the ORIGINAL file's folder, not the temp batch file.
            metadata = {
                "source": os.path.basename(file_path),
                "file_path": os.path.abspath(file_path),
            }
            batch_doc = docling_to_parsed_document(
                result=result, file_type="PDF", category="document", metadata=metadata,
                ro_start=ro_start, heading_stack=heading_stack,
                extract_images=extract_images,
            )

            # Fix page numbers
            for sec in batch_doc.sections:
                sec.page += start
            for tab in batch_doc.tables:
                tab.page += start
            for img in batch_doc.images:
                img.page += start
            for el in batch_doc.elements:
                el["location"]["page"] += start

            all_sections.extend(batch_doc.sections)
            all_tables.extend(batch_doc.tables)
            all_images.extend(batch_doc.images)
            all_elements.extend(batch_doc.elements)
            ro_start = getattr(batch_doc, "_next_ro", ro_start)

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

    extra = {"batch_size": BATCH_SIZE}
    if failed_pages:
        extra["failed_pages"] = failed_pages
    metadata = _rich_metadata(file_path, num_pages, extra)

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
        elements=all_elements,
    )

    # Rebuild heading levels + parent links from section numbering (whole doc).
    from app.services.providers.parsers.hierarchy import (
        build_hierarchy, build_section_hierarchy,
    )
    build_hierarchy(parsed_doc.elements)
    build_section_hierarchy(parsed_doc.sections)

    logger.info(f"[PDF_LOADER] Done: {parsed_doc.total_sections} sections, "
                f"{parsed_doc.total_tables} tables, {parsed_doc.total_images} images, "
                f"{len(all_elements)} elements")

    return {
        "raw_text": raw_text,
        "num_pages": num_pages,
        "file_type": "PDF",
        "category": "document",
        "metadata": metadata,
        "total_chars": len(raw_text),
        "parsed_document": parsed_doc.to_dict(),  # ← structure ready
    }