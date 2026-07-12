"""
Excel Parser — Table Document Model (openpyxl + pandas).

Builds workbook → sheet → table elements, plus `formula` and `merged_cell`
elements (with cell ranges) for citations. openpyxl reads the workbook
structure / formulas / merged cells; pandas types the tables. Also emits one
Table chunking block per sheet for the Chunking Factory.

(An optional ks-xlsx-parser layer could be slotted in front of openpyxl here;
openpyxl remains the reliable fallback.)
"""
import os
import logging
from app.services.providers.parsers.parsed_document import ParsedDocument, Section

logger = logging.getLogger(__name__)


def parse(loaded_data: dict) -> ParsedDocument:
    file_path = loaded_data.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise ValueError("Excel parser needs the original file (file_path)")

    logger.info("[EXCEL_PARSER] Parsing Excel → workbook/sheet/table elements")

    from app.services.providers.parsers.table_elements import build_excel_workbook
    elements, chunk_sections, engine = build_excel_workbook(file_path)
    logger.info(f"[EXCEL_PARSER] engine={engine}, {len(chunk_sections)} chunk section(s)")

    # ── Chunking: one Section per extracted block (ks-xlsx-parser chunks carry
    # their own cell-range citation in the text). ──
    sections = [Section(heading=h, content=c, level=1, page=1)
                for h, c in chunk_sections if c and c.strip()]

    wb = next((e for e in elements if e["type"] == "workbook"), None)
    meta = dict(loaded_data.get("metadata", {}))
    meta.update({"source_type": "xlsx", "encoding": "utf-8", "excel_engine": engine,
                 "sheets": wb["content"]["sheets"] if wb else []})

    return ParsedDocument(
        title=os.path.splitext(meta.get("source") or os.path.basename(file_path))[0],
        sections=sections, elements=elements, metadata=meta,
        num_pages=max(1, len(meta.get("sheets", []))),
        file_type="Excel", category="structured_data",
    )
