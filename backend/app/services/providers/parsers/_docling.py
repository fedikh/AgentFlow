"""
Docling → ParsedDocument converter.
Shared by PDF and DOCX parsers.
Now extracts images: saves to disk + stores caption/OCR text.
"""
import os
import logging
from app.services.providers.parsers.parsed_document import ParsedDocument, Section, Table, Image

logger = logging.getLogger(__name__)

HEADING_LABELS = {"title", "section_header", "page_header"}
TEXT_LABELS = {"text", "paragraph", "list_item", "caption", "footnote"}


def docling_to_parsed_document(result, file_type="PDF", category="document", metadata=None):
    doc = result.document

    sections = []
    tables = []
    images = []
    title = ""
    current_heading = ""
    current_level = 1
    current_lines = []
    current_page = 1
    img_counter = 0

    # Determine image save directory from file_path
    file_path = (metadata or {}).get("source", "")
    if not file_path:
        file_path = (metadata or {}).get("file_path", "")
    images_dir = _get_images_dir(file_path)

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

        # ── IMAGE ──
        if class_name == "PictureItem" or label in ("picture", "figure"):
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

            # Save image to disk if possible
            if images_dir:
                try:
                    image_path = _save_image(item, doc, images_dir, page, img_counter)
                except Exception as e:
                    logger.warning(f"Could not save image {img_counter}: {e}")

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
                # Image with no text — save path only for frontend display
                if image_path:
                    images.append(Image(
                        caption=f"Image on page {page}",
                        ocr_text="",
                        image_path=image_path,
                        page=page,
                        bbox=bbox,
                    ))

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
            continue

        # ── BODY TEXT ──
        if label in TEXT_LABELS or class_name == "TextItem":
            text = str(item.text).strip() if hasattr(item, 'text') and item.text else ""
            if text:
                current_lines.append(text)
                if not current_heading:
                    current_page = page
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
    )

    logger.info(f"[DOCLING] -> {parsed.total_sections} sections, "
                f"{parsed.total_tables} tables, {parsed.total_images} images")

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
    """Create images directory next to the uploaded file."""
    if not file_path:
        return ""
    parent = os.path.dirname(os.path.abspath(file_path))
    images_dir = os.path.join(parent, "images")
    return images_dir


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