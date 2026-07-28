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
    # 1) Numbered headings: "1. Title", "2) Title", "3.1 Title" — a strong signal.
    if re.match(r"^\d+(?:\.\d+)*[.)]?\s+\S", t):
        return True
    # 2) Short ALL-CAPS lines (a common heading/section style), e.g. "OBJECTIVE",
    #    "ISO 9001:2015 CERTIFIED", or a single glossary letter "A".
    #
    # Deliberately NOTHING else. The old rule "any short line without a full stop
    # is a heading" wrecked real documents: it turned names, addresses, phone
    # numbers and mid-sentence fragments into hundreds of level-1 headings. If a
    # DOCX uses real Word Heading styles, Docling labels them itself (we honour
    # that above); mixed-case plain-bold pseudo-headings are left as paragraphs —
    # a far safer default than mass false headings.
    letters = [c for c in t if c.isalpha()]
    if not letters or len(t.split()) > 8:
        return False
    if not all(c.isupper() for c in letters):
        return False
    # A comma usually means a list (credentials "PGDM, PGDCA", "AS 5, AS 9"),
    # not a heading — so require no comma.
    return "," not in t


def _table_structured(item, doc):
    """Return (headers, rows) for a docling TableItem. rows are keyed by COLUMN
    POSITION ("0".."N-1"), never by header text: Docling frequently emits
    duplicate or empty header names (a merged title cell repeated across every
    column, blank first columns, "0..6" placeholders), and keying rows by those
    names collapses several columns into one and loses data. Positional keys are
    always unique, so every cell survives. Falls back to ([], []) on failure."""
    try:
        df = item.export_to_dataframe(doc)
    except Exception:
        try:
            df = item.export_to_dataframe()
        except Exception:
            return [], []
    try:
        headers = [str(c) for c in df.columns]
        rows = []
        for rec in df.itertuples(index=False, name=None):
            rows.append({str(i): ("" if v is None else str(v)) for i, v in enumerate(rec)})
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


def _md_cols(content: dict) -> int:
    """Column count of a table content dict — from headers, else the first
    markdown row."""
    hs = content.get("headers") or []
    if hs:
        return len(hs)
    md = (content.get("markdown") or "").strip()
    if not md:
        return 0
    first = md.split("\n", 1)[0]
    return len([x for x in first.split("|") if x.strip()])


def _row_values(row):
    """Ordered cell values of a table row (dict -> values in insertion order)."""
    if isinstance(row, dict):
        return list(row.values())
    if isinstance(row, (list, tuple)):
        return list(row)
    return [row]


def _row_is_blank(row) -> bool:
    return all(not str(v).strip() for v in _row_values(row))


def _remap_row(row, ncols):
    """Re-key a row onto POSITIONAL keys "0".."ncols-1". Rows can arrive keyed by
    a half's own header names or by position; normalizing everything to column
    index makes merged halves line up column-for-column and never collide."""
    vals = _row_values(row)
    return {str(i): (vals[i] if i < len(vals) else "") for i in range(ncols)}


def _last_page(el) -> int:
    """Page of the LAST merged half (so a 3+ page table keeps chaining), falling
    back to the element's own page."""
    tp = el.get("_merge_tail_page")
    if tp:
        return tp
    return (el.get("location") or {}).get("page", 0) or 0


def _table_elements_mergeable(a, b) -> bool:
    """True if two consecutive table elements are the two halves of ONE table
    split across a page break. Requires matching column count. Across a page
    break (page diff 1) the continuation half often carries different or
    auto-generated headers (Docling emits "0..6" for one half and the real
    header names for the other), so a matching column count alone is enough
    there. On the SAME page we require identical headers, so two genuinely
    distinct stacked tables are not glued together."""
    ca, cb = a.get("content") or {}, b.get("content") or {}
    pa = _last_page(a)
    pb = (b.get("location") or {}).get("page", 0) or 0
    dp = pb - pa
    if dp not in (0, 1):
        return False
    na, nb = _md_cols(ca), _md_cols(cb)
    if not (na and na == nb):
        return False
    if dp == 1:
        return True                       # page-spanning continuation
    ha = [str(h).strip().lower() for h in (ca.get("headers") or [])]
    hb = [str(h).strip().lower() for h in (cb.get("headers") or [])]
    return bool(ha) and ha == hb


def _is_md_separator(line: str) -> bool:
    """True for a Markdown header-separator row like '|---|---|' (only |, -, :,
    spaces). The merged table keeps ONE such row at the top; any others coming
    from the continuation half must be dropped or the table renders broken."""
    s = (line or "").strip()
    if "-" not in s:
        return False
    return set(s) <= set("|:- ")


def _merge_table_content(a: dict, b: dict) -> None:
    """Merge table-content dict b INTO a. The structured `rows` (what the grid
    renders) are re-keyed onto a's header positions so the continuation half
    lines up column-for-column instead of rendering blank; fully-blank rows are
    dropped. The markdown is kept a single valid table (one separator, no
    duplicated header)."""
    ncols = _md_cols(a) or _md_cols(b)
    a_rows = a.get("rows") or []
    b_rows = b.get("rows") or []
    if ncols:
        a_rows = [_remap_row(r, ncols) for r in a_rows]
        b_rows = [_remap_row(r, ncols) for r in b_rows]
    merged = a_rows + b_rows
    a["rows"] = [r for r in merged if not _row_is_blank(r)]

    amd = (a.get("markdown") or "").rstrip()
    blines = (b.get("markdown") or "").strip().split("\n")
    ha = [str(h).strip().lower() for h in (a.get("headers") or [])]
    hb = [str(h).strip().lower() for h in (b.get("headers") or [])]
    # If the continuation repeats the same header, drop that leading header row
    # (its separator is removed below with any other separator lines).
    if ha and ha == hb and blines:
        blines = blines[1:]
    blines = [l for l in blines if l.strip() and not _is_md_separator(l)]
    tail = "\n".join(blines)
    a["markdown"] = (amd + ("\n" + tail if tail else "")).strip()
    if not a.get("headers") and b.get("headers"):
        a["headers"] = b["headers"]


def mark_repeated_boilerplate(elements: list) -> int:
    """Cross-page repetition detector — page furniture / boilerplate.

    Form documents (letters, certificates, invoices) repeat the SAME
    letterhead, dates and legal paragraphs on every page. The parse must stay
    FAITHFUL (the Parsed view shows everything), but chunking should not embed
    the same boilerplate once per page — it dilutes every chunk's meaning.

    Rule: an identical normalized paragraph appearing on 2+ DIFFERENT pages at
    roughly the same vertical position is furniture. The FIRST occurrence
    stays normal (the information remains answerable once); every repeat is
    tagged metadata.boilerplate=True and the chunking layer skips it.
    Headings are exempt — a repeated heading still anchors its page's section.
    """
    import re as _re
    from collections import defaultdict

    groups = defaultdict(list)
    for el in elements or []:
        if el.get("type") != "paragraph":
            continue
        txt = ((el.get("content") or {}).get("text") or "").strip()
        if len(txt) < 8:
            continue
        groups[_re.sub(r"\s+", " ", txt.lower())].append(el)

    marked = 0
    for key, els in groups.items():
        pages = {(e.get("location") or {}).get("page") for e in els}
        if len(pages) < 2:
            continue

        def _top(e):
            bb = (e.get("location") or {}).get("bbox") or []
            return bb[1] if len(bb) >= 2 else None

        tops = [v for v in (_top(e) for e in els) if v is not None]
        # same vertical band across pages (PDF), or short text when no bbox (DOCX)
        if tops:
            if max(tops) - min(tops) > 40:
                continue
        elif len(key) > 300:
            continue
        ordered_els = sorted(els, key=lambda x: (x.get("metadata") or {}).get("reading_order", 0))
        for e in ordered_els[1:]:
            e.setdefault("metadata", {})["boilerplate"] = True
            marked += 1
    return marked


def merge_split_tables(elements: list) -> list:
    """Merge consecutive table ELEMENTS that are halves of a page-spanning table.
    Handles both Docling's per-page split and our page-batch boundary split, and
    tables that run across 3+ pages (each half chains onto the previous)."""
    out = []
    for el in (elements or []):
        if (el.get("type") == "table" and out and out[-1].get("type") == "table"
                and _table_elements_mergeable(out[-1], el)):
            _merge_table_content(out[-1].setdefault("content", {}), el.get("content") or {})
            out[-1]["_merge_tail_page"] = (el.get("location") or {}).get("page")
            continue
        out.append(el)
    for el in out:                       # strip internal bookkeeping
        el.pop("_merge_tail_page", None)
    return out


def merge_split_tables_legacy(tables: list) -> list:
    """Same merge for the legacy Table objects (content markdown + rows + page)."""
    out = []
    for t in tables:
        if out:
            prev = out[-1]
            dp = (getattr(t, "page", 0) or 0) - (getattr(prev, "page", 0) or 0)
            ph = [str(h).strip().lower() for h in (getattr(prev, "headers", []) or [])]
            th = [str(h).strip().lower() for h in (getattr(t, "headers", []) or [])]
            cols_prev = len(ph) or _md_cols({"markdown": getattr(prev, "content", "") or ""})
            cols_t = len(th) or _md_cols({"markdown": getattr(t, "content", "") or ""})
            cols_match = bool(cols_prev) and cols_prev == cols_t
            # page-spanning (dp==1): column count is enough; same page (dp==0):
            # require identical headers so distinct stacked tables stay separate.
            mergeable = cols_match and (dp == 1 or (dp == 0 and ph and ph == th))
            if mergeable:
                pmd = (getattr(prev, "content", "") or "").rstrip()
                blines = (getattr(t, "content", "") or "").strip().split("\n")
                if ph and ph == th and blines:
                    blines = blines[1:]
                blines = [l for l in blines if l.strip() and not _is_md_separator(l)]
                tail = "\n".join(blines)
                prev.content = (pmd + ("\n" + tail if tail else "")).strip()
                ncols = (len(ph) or _md_cols({"markdown": getattr(prev, "content", "") or ""})
                         or len(th) or _md_cols({"markdown": getattr(t, "content", "") or ""}))
                prev_rows = getattr(prev, "rows", []) or []
                new_rows = getattr(t, "rows", []) or []
                if ncols:
                    prev_rows = [_remap_row(r, ncols) for r in prev_rows]
                    new_rows = [_remap_row(r, ncols) for r in new_rows]
                merged = prev_rows + new_rows
                prev.rows = [r for r in merged if not _row_is_blank(r)]
                prev.num_rows = len(prev.rows)
                continue
        out.append(t)
    return out


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
