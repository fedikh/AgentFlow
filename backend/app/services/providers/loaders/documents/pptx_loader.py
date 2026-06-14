"""
PPTX Loader — python-pptx with deep text extraction.
Extracts text from ALL shapes including grouped shapes.
"""
import os
import logging
from pptx import Presentation
from pptx.util import Inches
from app.services.providers.parsers.parsed_document import ParsedDocument, Section, Table

logger = logging.getLogger(__name__)


def load(file_path: str) -> dict:
    logger.info(f"[PPTX_LOADER] Loading: {os.path.basename(file_path)}")

    prs = Presentation(file_path)
    sections = []
    tables = []
    raw_parts = []

    for i, slide in enumerate(prs.slides, 1):
        slide_title = ""
        slide_body = []
        slide_raw = [f"[Slide {i}]"]

        # Extract ALL text from ALL shapes (including groups)
        for shape in slide.shapes:
            _extract_shape(shape, slide_title, slide_body, slide_raw, tables, i)

        # Detect title: first text that looks like a title
        # (short, often the first text on the slide)
        if not slide_title:
            # Try shapes.title first
            if slide.shapes.title and slide.shapes.title.text.strip():
                slide_title = slide.shapes.title.text.strip()

        # If still no title, use first short line as title
        if not slide_title and slide_body:
            first = slide_body[0]
            if len(first) < 100:
                slide_title = first
                slide_body = slide_body[1:]

        if slide_title:
            slide_raw.insert(1, slide_title)

        raw_parts.extend(slide_raw)

        # Speaker notes
        notes = ""
        try:
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    slide_body.append(f"[Notes: {notes}]")
                    raw_parts.append(f"[Notes: {notes}]")
        except Exception:
            pass

        # Create section
        content = "\n".join(slide_body).strip()
        if content or slide_title:
            sections.append(Section(
                heading=slide_title or f"Slide {i}",
                content=content if content else "(empty slide)",
                level=1,
                page=i,
            ))

    # Raw text
    raw_text = "\n\n".join(raw_parts)
    from app.services.providers.loaders._utils import clean_text
    raw_text = clean_text(raw_text)

    if not raw_text.strip():
        raise ValueError("PPTX contains no readable text")

    num_slides = len(prs.slides)

    parsed_doc = ParsedDocument(
        title=sections[0].heading if sections else "",
        sections=sections,
        tables=tables,
        metadata={"source": os.path.basename(file_path), "parser": "python-pptx", "num_slides": num_slides},
        num_pages=num_slides,
        file_type="PPTX",
        category="document",
    )

    logger.info(f"[PPTX_LOADER] {num_slides} slides → {len(sections)} sections, {len(tables)} tables")

    return {
        "raw_text": raw_text,
        "num_pages": num_slides,
        "file_type": "PPTX",
        "category": "document",
        "metadata": {"source": os.path.basename(file_path), "parser": "python-pptx", "num_slides": num_slides},
        "total_chars": len(raw_text),
        "parsed_document": parsed_doc.to_dict(),
    }


def _extract_shape(shape, title, body, raw, tables, slide_num):
    """Recursively extract text from any shape (including groups)."""

    # Grouped shapes — recurse into each
    if shape.shape_type == 6:  # MSO_SHAPE_TYPE.GROUP
        for child in shape.shapes:
            _extract_shape(child, title, body, raw, tables, slide_num)
        return

    # Tables
    if shape.has_table:
        table = shape.table
        headers = [cell.text.strip() for cell in table.rows[0].cells]
        rows_data = []
        md = ["| " + " | ".join(headers) + " |"]
        md.append("| " + " | ".join("---" for _ in headers) + " |")

        for row in list(table.rows)[1:]:
            cells = [cell.text.strip() for cell in row.cells]
            rows_data.append(cells)
            md.append("| " + " | ".join(cells) + " |")

        table_md = "\n".join(md)
        raw.append(table_md)

        tables.append(Table(
            content=table_md,
            headers=headers,
            rows=rows_data,
            num_rows=len(rows_data),
            num_cols=len(headers),
            page=slide_num,
        ))
        return

    # Text frames
    if shape.has_text_frame:
        for para in shape.text_frame.paragraphs:
            text = para.text.strip()
            if text:
                body.append(text)
                raw.append(text)