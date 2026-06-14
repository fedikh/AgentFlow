"""
TXT Parser — paragraph-based splitting, produces ParsedDocument.
"""
import re
import logging
from app.services.providers.parsers.parsed_document import ParsedDocument, Section

logger = logging.getLogger(__name__)


def parse(loaded_data: dict) -> ParsedDocument:
    raw_text = loaded_data.get("raw_text", "")
    if not raw_text.strip():
        raise ValueError("No text to parse")

    logger.info(f"[TXT_PARSER] Parsing {len(raw_text)} chars")

    paragraphs = re.split(r'\n\s*\n', raw_text)
    sections = []
    current_heading = ""

    for para in paragraphs:
        para = para.strip()
        if not para or len(para) <= 5:
            continue

        first_line = para.split("\n")[0].strip()
        if _is_heading(first_line):
            current_heading = first_line
            rest = "\n".join(para.split("\n")[1:]).strip()
            if rest and len(rest) > 5:
                sections.append(Section(heading=current_heading, content=rest, page=1))
        else:
            sections.append(Section(heading=current_heading, content=para, page=1))

    return ParsedDocument(
        sections=sections,
        metadata=loaded_data.get("metadata", {}),
        file_type="Text",
        category="document",
    )


def _is_heading(line):
    if len(line) > 80: return False
    if line.isupper() and len(line) > 3: return True
    if re.match(r"^\d+[\.\)]\s+[A-ZÀ-Ü]", line): return True
    if line.endswith(":") and len(line) < 60: return True
    return False