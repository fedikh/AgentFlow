"""
HTML Parser — paragraph splitting, produces ParsedDocument.
"""
import re
import logging
from app.services.providers.parsers.parsed_document import ParsedDocument, Section, Table

logger = logging.getLogger(__name__)


def parse(loaded_data: dict) -> ParsedDocument:
    raw_text = loaded_data.get("raw_text", "")
    if not raw_text.strip():
        raise ValueError("No HTML content")

    logger.info(f"[HTML_PARSER] Parsing {len(raw_text)} chars")

    paragraphs = re.split(r'\n\s*\n', raw_text)
    sections = []
    tables = []

    for para in paragraphs:
        para = para.strip()
        if not para or len(para) <= 10:
            continue
        lines = para.split("\n")
        if len(lines) > 1 and sum(1 for l in lines if "|" in l) / len(lines) > 0.6:
            tables.append(Table(content=para, page=1))
        else:
            sections.append(Section(heading="", content=para, page=1))

    return ParsedDocument(
        title=loaded_data.get("metadata", {}).get("title", ""),
        sections=sections, tables=tables,
        metadata=loaded_data.get("metadata", {}),
        file_type="HTML", category="web",
    )