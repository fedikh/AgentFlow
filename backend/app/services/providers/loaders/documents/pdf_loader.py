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

    # Pages per Docling run — smaller = lower peak memory (avoids std::bad_alloc).
    batch_size = max(1, int(getattr(settings, "DOCLING_BATCH_SIZE", BATCH_SIZE)))

    if num_pages <= batch_size:
        logger.info(f"[PDF_LOADER] {num_pages} pages -> direct")
        try:
            return _load_single(converter, file_path, num_pages, extract_images)
        except Exception as e:
            # Small PDF that OOMs/fails in one shot → retry page-by-page (with
            # the text fallback + backfill), so it doesn't just error out.
            logger.warning(f"[PDF_LOADER] single-shot failed ({e}); retrying per-page")
            return _load_batched(converter, file_path, num_pages, extract_images, 1)
    else:
        logger.info(f"[PDF_LOADER] {num_pages} pages -> batched ({batch_size}/batch)")
        return _load_batched(converter, file_path, num_pages, extract_images, batch_size)


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

    # Safety net: recover any page Docling skipped (text backfill → vision OCR).
    still_missing = _recover_pages(parsed_doc, file_path, num_pages)
    if still_missing:
        parsed_doc.metadata = {**(parsed_doc.metadata or {}), "failed_pages": still_missing}
    if not raw_text.strip():
        raw_text = "\n\n".join(s.content for s in parsed_doc.sections).strip()
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


def _convert_range(converter, src, start, end, file_path, extract_images,
                   ro_start, heading_stack):
    """Convert pages [start, end) with Docling → (batch_doc, raw_markdown).

    Page numbers are offset by `start`. Raises on failure (e.g. std::bad_alloc)
    so the caller can retry a smaller range. Always cleans up its temp file.
    """
    import fitz
    from app.services.providers.parsers._docling import docling_to_parsed_document

    tmp_path = None
    try:
        tmp = fitz.open()
        tmp.insert_pdf(src, from_page=start, to_page=end - 1)
        tmp_path = tempfile.mktemp(suffix=".pdf")
        tmp.save(tmp_path)
        tmp.close()

        result = converter.convert(tmp_path)
        batch_text = (result.document.export_to_markdown() or "").strip()

        # real file_path → images save under the ORIGINAL file's folder
        metadata = {
            "source": os.path.basename(file_path),
            "file_path": os.path.abspath(file_path),
        }
        batch_doc = docling_to_parsed_document(
            result=result, file_type="PDF", category="document", metadata=metadata,
            ro_start=ro_start, heading_stack=heading_stack,
            extract_images=extract_images, page_offset=start,   # global image filenames
        )
        for sec in batch_doc.sections:
            sec.page += start
        for tab in batch_doc.tables:
            tab.page += start
        for img in batch_doc.images:
            img.page += start
        for el in batch_doc.elements:
            el["location"]["page"] += start
        return batch_doc, batch_text
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _covered_pages(parsed_doc) -> set:
    """Pages that produced at least one piece of content."""
    cov = set()
    for s in parsed_doc.sections:
        cov.add(s.page)
    for t in parsed_doc.tables:
        cov.add(t.page)
    for im in parsed_doc.images:
        cov.add(im.page)
    for el in (parsed_doc.elements or []):
        p = (el.get("location") or {}).get("page")
        if p:
            cov.add(p)
    return cov


def _backfill_pages(parsed_doc, file_path, num_pages) -> list:
    """Guarantee every page is represented. Docling can silently yield nothing
    for a page (layout failure with no error), which would drop that page from
    the index. For each uncovered page we pull its text with PyMuPDF and append
    a section + element, so no page with a text layer is ever skipped.

    Returns the list of page numbers that were backfilled.
    """
    import fitz
    from app.services.providers.parsers.parsed_document import Section

    covered = _covered_pages(parsed_doc)
    missing = [p for p in range(1, num_pages + 1) if p not in covered]
    if not missing:
        return []

    ro = getattr(parsed_doc, "_next_ro", 0) or max(
        [(el.get("metadata") or {}).get("reading_order", 0)
         for el in (parsed_doc.elements or [])] or [0])

    added = []
    try:
        src = fitz.open(file_path)
    except Exception:
        return []
    try:
        for p in missing:
            try:
                text = src[p - 1].get_text("text", sort=True).strip()
            except Exception:
                text = ""
            if not text:
                continue      # image-only / scanned page (no text layer) — needs OCR
            ro += 1
            parsed_doc.sections.append(Section(heading="", content=text, level=1, page=p))
            if parsed_doc.elements is not None:
                parsed_doc.elements.append({
                    "id": f"e{ro}", "type": "paragraph", "content": {"text": text},
                    "location": {"page": p, "bbox": []},
                    "hierarchy": {"parent": None},
                    "metadata": {"reading_order": ro},
                })
            added.append(p)
    finally:
        src.close()

    if added:
        parsed_doc._next_ro = ro
        # keep everything in page order (backfilled pages were appended at the end)
        parsed_doc.sections.sort(key=lambda s: s.page)
        if parsed_doc.elements:
            parsed_doc.elements.sort(
                key=lambda e: ((e.get("location") or {}).get("page", 0),
                               (e.get("metadata") or {}).get("reading_order", 0)))
    return added


def _ocr_missing_pages(parsed_doc, file_path, num_pages) -> list:
    """Last resort for pages with NO text layer (scanned / image-only): render
    each still-empty page and OCR it with the vision model, so no page is
    skipped. Requires a vision key; fails soft (returns []) otherwise. Bounded by
    PDF_OCR_MAX_PAGES. Returns the list of pages recovered."""
    from app.config import settings
    missing = sorted(set(range(1, num_pages + 1)) - _covered_pages(parsed_doc))
    if not missing:
        return []

    import fitz
    from app.services.providers.parsers.parsed_document import Section
    from app.services.providers.parsers.image_summarizer import transcribe_image

    cap = int(getattr(settings, "PDF_OCR_MAX_PAGES", 60))
    todo = missing[:cap]
    ro = getattr(parsed_doc, "_next_ro", 0) or 0
    added = []
    try:
        src = fitz.open(file_path)
    except Exception:
        return []
    try:
        for p in todo:
            tmp = None
            try:
                pix = src[p - 1].get_pixmap(dpi=200)   # crisp enough for OCR
                tmp = tempfile.mktemp(suffix=".png")
                pix.save(tmp)
                text = (transcribe_image(tmp) or "").strip()
            except Exception as e:
                logger.warning(f"[PDF_LOADER] OCR render/read failed p{p}: {e}")
                text = ""
            finally:
                if tmp and os.path.exists(tmp):
                    os.unlink(tmp)
            if not text:
                continue
            ro += 1
            parsed_doc.sections.append(Section(heading="", content=text, level=1, page=p))
            if parsed_doc.elements is not None:
                parsed_doc.elements.append({
                    "id": f"e{ro}", "type": "paragraph", "content": {"text": text},
                    "location": {"page": p, "bbox": []},
                    "hierarchy": {"parent": None},
                    "metadata": {"reading_order": ro, "source": "ocr"},
                })
            added.append(p)
    finally:
        src.close()

    if added:
        parsed_doc._next_ro = ro
        parsed_doc.sections.sort(key=lambda s: s.page)
        if parsed_doc.elements:
            parsed_doc.elements.sort(
                key=lambda e: ((e.get("location") or {}).get("page", 0),
                               (e.get("metadata") or {}).get("reading_order", 0)))
    if len(missing) > len(todo):
        logger.warning(f"[PDF_LOADER] OCR fallback capped at {cap} pages; "
                       f"{len(missing) - len(todo)} pages still empty")
    return added


def _recover_pages(parsed_doc, file_path, num_pages) -> list:
    """Ensure every page is represented: PyMuPDF text backfill for silent Docling
    misses, then vision-OCR for scanned / image-only pages. Sets ocr_quality /
    ocr_issues and returns pages that are STILL empty (needed better OCR)."""
    from app.config import settings
    bf = _backfill_pages(parsed_doc, file_path, num_pages)
    if bf:
        logger.info(f"[PDF_LOADER] backfilled text for skipped pages {bf}")
    if getattr(settings, "PDF_OCR_FALLBACK", True):
        oc = _ocr_missing_pages(parsed_doc, file_path, num_pages)
        if oc:
            logger.info(f"[PDF_LOADER] OCR-recovered scanned pages {oc}")
    still = sorted(set(range(1, num_pages + 1)) - _covered_pages(parsed_doc))
    parsed_doc.ocr_quality = "good" if not still else "fair"
    parsed_doc.ocr_issues = (
        [f"Pages still empty after OCR: {still}"] if still else [])
    return still


def _fitz_text_page(src, page_idx, ro_start, global_page):
    """Last-resort: extract ONE page's text with PyMuPDF (no ML) when Docling
    fails on it, so the page's content is indexed instead of skipped. Returns
    (section | None, [elements], next_ro)."""
    from app.services.providers.parsers.parsed_document import Section
    try:
        text = src[page_idx].get_text("text", sort=True).strip()
    except Exception:
        text = ""
    if not text:
        return None, [], ro_start
    ro = ro_start + 1
    el = {
        "id": f"e{ro}", "type": "paragraph", "content": {"text": text},
        "location": {"page": global_page, "bbox": []},
        "hierarchy": {"parent": None},
        "metadata": {"reading_order": ro},
    }
    return Section(heading="", content=text, level=1, page=global_page), [el], ro


def _load_batched(converter, file_path, num_pages, extract_images=True, batch_size=BATCH_SIZE):
    """Load a large PDF in batches, with page-by-page recovery on OOM.

    A batch that fails (typically std::bad_alloc when Docling can't allocate the
    page bitmaps) is retried one page at a time — a single page needs far less
    memory — so pages are recovered instead of silently dropped."""
    import fitz
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

    def _merge(batch_doc, batch_text):
        nonlocal ro_start, title
        if batch_text:
            all_raw_parts.append(batch_text)
        all_sections.extend(batch_doc.sections)
        all_tables.extend(batch_doc.tables)
        all_images.extend(batch_doc.images)
        all_elements.extend(batch_doc.elements)
        ro_start = getattr(batch_doc, "_next_ro", ro_start)
        if not title and batch_doc.title:
            title = batch_doc.title

    src = fitz.open(file_path)

    for start in range(0, num_pages, batch_size):
        end = min(start + batch_size, num_pages)
        logger.info(f"[PDF_LOADER] Batch: pages {start + 1}–{end}")
        try:
            batch_doc, batch_text = _convert_range(
                converter, src, start, end, file_path, extract_images,
                ro_start, heading_stack)
            _merge(batch_doc, batch_text)
        except Exception as e:
            # Retry the batch page-by-page so an OOM doesn't drop whole pages.
            if end - start > 1:
                logger.warning(f"[PDF_LOADER] Batch {start + 1}–{end} failed "
                               f"({e}); retrying page-by-page")
                for p in range(start, end):
                    gc.collect()
                    try:
                        bd, bt = _convert_range(
                            converter, src, p, p + 1, file_path, extract_images,
                            ro_start, heading_stack)
                        _merge(bd, bt)
                    except Exception as e2:
                        # Docling failed on this page too → keep its text at least.
                        sec, els, ro_start = _fitz_text_page(src, p, ro_start, p + 1)
                        if sec:
                            logger.warning(f"[PDF_LOADER] Page {p + 1} Docling failed "
                                           f"({e2}); kept text via PyMuPDF")
                            all_sections.append(sec)
                            all_elements.extend(els)
                            all_raw_parts.append(sec.content)
                        else:
                            logger.warning(f"[PDF_LOADER] Page {p + 1} failed: {e2}")
                            failed_pages.append(p + 1)
            else:
                # single-page batch failed → text fallback before giving up
                sec, els, ro_start = _fitz_text_page(src, start, ro_start, start + 1)
                if sec:
                    logger.warning(f"[PDF_LOADER] Page {start + 1} Docling failed "
                                   f"({e}); kept text via PyMuPDF")
                    all_sections.append(sec)
                    all_elements.extend(els)
                    all_raw_parts.append(sec.content)
                else:
                    logger.warning(f"[PDF_LOADER] Page {start + 1} failed: {e}")
                    failed_pages.append(start + 1)
        finally:
            gc.collect()

    src.close()

    raw_text = "\n\n".join(all_raw_parts)
    from app.services.providers.loaders._utils import clean_text
    raw_text = clean_text(raw_text)

    if not raw_text.strip() and not all_sections:
        raise ValueError("PDF contains no readable text")

    parsed_doc = ParsedDocument(
        title=title,
        sections=all_sections,
        tables=all_tables,
        images=all_images,
        metadata={},
        num_pages=num_pages,
        file_type="PDF",
        category="document",
        elements=all_elements,
    )
    parsed_doc._next_ro = ro_start

    # Safety net: recover any skipped page (text backfill → vision OCR). Sets
    # ocr_quality / ocr_issues and returns pages that are STILL empty.
    still_missing = _recover_pages(parsed_doc, file_path, num_pages)
    if not raw_text.strip():
        raw_text = "\n\n".join(s.content for s in parsed_doc.sections).strip()

    extra = {"batch_size": batch_size}
    if still_missing:
        extra["failed_pages"] = still_missing
    parsed_doc.metadata = _rich_metadata(file_path, num_pages, extra)

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
        "metadata": parsed_doc.metadata,
        "total_chars": len(raw_text),
        "parsed_document": parsed_doc.to_dict(),  # ← structure ready
    }