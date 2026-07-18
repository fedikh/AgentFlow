"""
Docling → ParsedDocument converter.
Shared by PDF, DOCX and PPTX parsers.
Extracts images (saves to disk + stores caption/OCR text) and builds sections.

Format-aware structuring:
  * PDF  → Docling labels headings from layout.
  * DOCX → headings inferred from text (Word files often use plain bold
           paragraphs instead of real Heading styles).
  * PPTX → one section per slide (split when the page/slide number changes).
"""
import os
import re
import logging
from app.services.providers.parsers.parsed_document import ParsedDocument, Section, Table, Image

logger = logging.getLogger(__name__)

HEADING_LABELS = {"title", "section_header", "page_header"}
TEXT_LABELS = {"text", "paragraph", "list_item", "caption", "footnote"}


def _looks_like_heading(text: str) -> bool:
    """
    Heuristic heading detection for formats where Docling can't label headings
    (e.g. DOCX written with plain bold paragraphs instead of Heading styles).
    Approximates PDF-like sectioning. Kept conservative to avoid over-splitting.
    """
    t = (text or "").strip()
    if not t or len(t) > 90:
        return False
    # Numbered headings: "1. Title", "2) Title", "3.1 Title"
    if re.match(r"^\d+(?:\.\d+)*[.)]?\s+\S", t):
        return True
    # Short, title-like line that isn't a full sentence
    words = t.split()
    if len(words) <= 8 and not t.endswith((".", ":", ";", ",", "!", "?")):
        return True
    return False


def _table_structured(item, doc):
    """Return (headers, rows) for a docling TableItem. rows = list of dicts keyed
    by header. Falls back to ([], []) if the table can't be structured."""
    try:
        df = item.export_to_dataframe(doc)
    except Exception:
        try:
            df = item.export_to_dataframe()
        except Exception:
            return [], []
    try:
        headers = [str(c) for c in df.columns]
        rows = [
            {str(k): ("" if v is None else str(v)) for k, v in rec.items()}
            for rec in df.to_dict(orient="records")
        ]
        return headers, rows
    except Exception:
        return [], []


def _caption_text(item, doc):
    """Best-effort caption for a table/picture item."""
    try:
        c = item.caption_text(doc)
        if c:
            return str(c).strip()
    except Exception:
        pass
    return ""


def docling_to_parsed_document(result, file_type="PDF", category="document",
                               metadata=None, ro_start=0, heading_stack=None,
                               extract_images=True, page_offset=0):
    """Convert a Docling result → ParsedDocument.

    page_offset: added to every page number so that, when a large PDF is parsed
    in batches, image filenames use the GLOBAL page number. Without it, each
    batch restarts page numbering at 1 and later batches overwrite earlier
    batches' image files (missing / duplicated images).
    """
    doc = result.document

    # ── Element-based output (new schema), built in the SAME pass ──
    # ids are global via ro_start; parent references use a heading stack that can
    # be carried across batches (so a paragraph's parent heading resolves even
    # when the heading was in an earlier batch).
    elements = []
    reading_order = ro_start
    if heading_stack is None:
        heading_stack = []

    def _emit(el_type, content, page, bbox, level=None, list_level=None):
        nonlocal reading_order
        reading_order += 1
        eid = f"e{reading_order}"
        if el_type == "heading":
            lvl = level or 1
            while heading_stack and heading_stack[-1][0] >= lvl:
                heading_stack.pop()
            parent = heading_stack[-1][1] if heading_stack else None
            heading_stack.append((lvl, eid))
        else:
            parent = heading_stack[-1][1] if heading_stack else None
        el = {
            "id": eid,
            "type": el_type,
            "content": content,
            "location": {"page": page, "bbox": bbox or []},
            "hierarchy": {"parent": parent},
            "metadata": {"reading_order": reading_order},
        }
        if level is not None:
            el["level"] = level
        if list_level is not None:
            el["metadata"]["list_level"] = list_level
        elements.append(el)
        return eid

    sections = []
    tables = []
    images = []
    title = ""
    current_heading = ""
    current_level = 1
    current_lines = []
    current_page = 1
    img_counter = 0
    seen_images = set()   # (global_page, bbox) → de-dupe pictures Docling yields twice

    # Determine image save directory from file_path
    file_path = (metadata or {}).get("file_path", "")
    if not file_path:
        file_path = (metadata or {}).get("source", "")
    images_dir = _get_images_dir(file_path)

    # Format-aware structuring (PDF already gets headings from layout):
    #   DOCX → infer headings from text (plain-paragraph docs)
    #   PPTX → one section per slide (split when the page/slide changes)
    detect_headings = str(file_type).upper() in ("WORD", "DOCX")
    split_on_page   = str(file_type).upper() == "PPTX"

    for item, level in doc.iterate_items():
        class_name = type(item).__name__
        label = ""
        if hasattr(item, 'label'):
            label = str(item.label).lower().split(".")[-1]

        # Skip non-content
        if label in ("page_footer", "page_number"):
            continue

        # Get page number
        page = 1
        bbox = []
        if hasattr(item, 'prov') and item.prov:
            for prov in item.prov:
                if hasattr(prov, 'page_no'):
                    page = prov.page_no
                if hasattr(prov, 'bbox'):
                    try:
                        b = prov.bbox
                        bbox = [b.l, b.t, b.r, b.b] if hasattr(b, 'l') else list(b)
                    except Exception:
                        bbox = []
                break

        # global page number (batch-local page + this batch's offset)
        gpage = page + page_offset

        # ── IMAGE ──
        if class_name == "PictureItem" or label in ("picture", "figure"):
            # Image extraction disabled for this doc → skip entirely: don't save
            # to disk and don't emit an image element (was previously extracted
            # anyway and only dropped afterward, leaving files + elements behind).
            if not extract_images:
                continue
            # De-dupe: some PDFs surface the same picture twice (same page+bbox).
            if bbox:
                dkey = (gpage, tuple(round(x, 1) for x in bbox))
                if dkey in seen_images:
                    continue
                seen_images.add(dkey)
            img_counter += 1
            caption = ""
            ocr_text = ""
            image_path = ""

            # Get caption
            if hasattr(item, 'caption') and item.caption:
                caption = str(item.caption).strip()
            elif hasattr(item, 'text') and item.text:
                caption = str(item.text).strip()

            # Get OCR text from image
            if hasattr(item, 'annotations'):
                for ann in item.annotations:
                    if hasattr(ann, 'text') and ann.text:
                        ocr_text += ann.text + " "
            ocr_text = ocr_text.strip()

            # Try to get caption from nearby elements
            if not caption and hasattr(item, 'captions'):
                try:
                    for cap in item.captions:
                        if hasattr(cap, 'text'):
                            caption = str(cap.text).strip()
                            break
                except Exception:
                    pass

            # Save image to disk if possible. Filename uses the GLOBAL page so
            # batches never overwrite each other (was the missing/duplicate bug).
            if images_dir:
                try:
                    image_path = _save_image(item, doc, images_dir, gpage, img_counter)
                except Exception as e:
                    logger.warning(f"Could not save image p{gpage} #{img_counter}: {e}")

            # Only add if we have SOME text (caption or OCR)
            if caption or ocr_text:
                images.append(Image(
                    caption=caption,
                    ocr_text=ocr_text,
                    image_path=image_path,
                    page=page,
                    bbox=bbox,
                ))
            else:
                # Image with no text — save path only for frontend display.
                # NOTE (Batch 2): the caption no longer embeds a page number.
                # It was a placeholder that could disagree with the real `page`
                # field (esp. for DOCX/PPTX). The real description comes from
                # Gemini's text_for_embedding at summarization time.
                if image_path:
                    images.append(Image(
                        caption="Image",
                        ocr_text="",
                        image_path=image_path,
                        page=page,
                        bbox=bbox,
                    ))

            if image_path or caption or ocr_text:
                _emit("image", {
                    "image_path": image_path,
                    "caption": caption or "Image",
                    "text_for_embedding": "",
                    "ocr_text": ocr_text,
                }, page, bbox)
            continue

        # ── TABLE ──
        if class_name == "TableItem" or label == "table":
            _flush(sections, current_heading, current_lines, current_level, current_page)
            current_lines = []

            text = ""
            if hasattr(item, 'text') and item.text:
                text = str(item.text).strip()
            try:
                md = item.export_to_markdown(doc).strip()
                if md:
                    text = md
            except Exception:
                pass

            if text:
                headers = _extract_headers(text)
                tables.append(Table(
                    content=text, headers=headers,
                    num_rows=_count_rows(text), num_cols=len(headers), page=page,
                ))
                s_headers, s_rows = _table_structured(item, doc)
                _emit("table", {
                    "caption": _caption_text(item, doc),
                    "headers": s_headers or headers,
                    "rows": s_rows,
                    "markdown": text,
                }, page, bbox)
            continue

        # ── HEADING ──
        if label in HEADING_LABELS:
            text = str(item.text).strip() if hasattr(item, 'text') and item.text else ""
            if not text:
                continue

            _flush(sections, current_heading, current_lines, current_level, current_page)
            current_lines = []
            current_heading = text
            current_level = level if level else 1
            current_page = page
            if not title:
                title = text
            _emit("heading", {"text": text}, page, bbox, level=current_level)
            continue

        # ── BODY TEXT ──
        if label in TEXT_LABELS or class_name == "TextItem":
            text = str(item.text).strip() if hasattr(item, 'text') and item.text else ""
            if text:
                # A Docling-labelled list item is NEVER a heading — the DOCX
                # heading heuristic would otherwise misread short bullets
                # (e.g. "Fixed Chunking (taille fixe)") as section titles and
                # drop their content.
                is_list = (label == "list_item" or class_name == "ListItem")

                # DOCX: treat heading-like lines as section headers so the
                # output is structured like a PDF (Docling can't label them).
                if detect_headings and not is_list and _looks_like_heading(text):
                    _flush(sections, current_heading, current_lines, current_level, current_page)
                    current_lines = []
                    current_heading = text
                    current_level = 1
                    current_page = page
                    if not title:
                        title = text
                    _emit("heading", {"text": text}, page, bbox, level=1)
                    continue

                # PPTX: start a new section whenever the slide (page) changes.
                if split_on_page and current_lines and page != current_page:
                    _flush(sections, current_heading, current_lines, current_level, current_page)
                    current_lines = []
                    current_heading = ""

                current_lines.append(text)
                if not current_heading:
                    current_page = page
                # Docling nests lists via `level` (1 = body, 2 = first bullet
                # level, 3 = sub-bullet …) → expose depth so nested items indent.
                _emit("list_item" if is_list else "paragraph",
                      {"text": text}, page, bbox,
                      list_level=(max(1, level - 1) if is_list else None))
            continue

    # Flush last section
    _flush(sections, current_heading, current_lines, current_level, current_page)

    num_pages = 1
    all_pages = [s.page for s in sections] + [t.page for t in tables] + [i.page for i in images]
    if all_pages:
        num_pages = max(all_pages)

    parsed = ParsedDocument(
        title=title,
        sections=sections,
        tables=tables,
        images=images,
        metadata=metadata or {},
        num_pages=num_pages,
        file_type=file_type,
        category=category,
        ocr_quality="good",
        ocr_issues=[],
        elements=elements,
    )
    # Carried across batches so ids/reading_order stay globally unique and the
    # heading stack (parent resolution) survives batch boundaries.
    parsed._next_ro = reading_order

    logger.info(f"[DOCLING] -> {parsed.total_sections} sections, "
                f"{parsed.total_tables} tables, {parsed.total_images} images, "
                f"{len(elements)} elements")

    return parsed


def _save_image(item, doc, images_dir, page, counter):
    """Try to save the image to disk. Returns the saved path or empty string."""
    os.makedirs(images_dir, exist_ok=True)
    filename = f"page{page}_img{counter}.png"
    save_path = os.path.join(images_dir, filename)

    # Method 1: Docling's get_image
    if hasattr(item, 'get_image'):
        try:
            pil_image = item.get_image(doc)
            if pil_image:
                pil_image.save(save_path)
                return save_path
        except Exception:
            pass

    # Method 2: item.image attribute
    if hasattr(item, 'image') and item.image:
        try:
            item.image.save(save_path)
            return save_path
        except Exception:
            pass

    # Method 3: export_to_markdown might give base64
    # Skip — not reliable

    return ""


def _get_images_dir(file_path):
    """Per-document images directory next to the uploaded file.

    Scoped as uploads/{space_id}/images/{file_stem}/ so that (a) two documents
    in the same space never overwrite each other's page images, and (b) deleting
    a document can drop all of its images by removing this single folder.
    """
    if not file_path:
        return ""
    parent = os.path.dirname(os.path.abspath(file_path))
    stem = os.path.splitext(os.path.basename(file_path))[0]
    if not stem:
        return os.path.join(parent, "images")
    return os.path.join(parent, "images", stem)


def _flush(sections, heading, lines, level, page):
    if not lines:
        return
    content = "\n".join(lines).strip()
    if content and len(content) > 5:
        sections.append(Section(heading=heading, content=content, level=level, page=page))


def _extract_headers(text):
    lines = text.strip().split("\n")
    if not lines:
        return []
    if "|" in lines[0]:
        return [h.strip() for h in lines[0].split("|") if h.strip()]
    return []


def _count_rows(text):
    return max(0, len(text.strip().split("\n")) - 2)
