"""
Markdown Parser — splits by # heading syntax, produces ParsedDocument.
"""
import re
import logging
from app.services.providers.parsers.parsed_document import ParsedDocument, Section, Table

logger = logging.getLogger(__name__)


def parse(loaded_data: dict) -> ParsedDocument:
    raw_text = loaded_data.get("raw_text", "")
    if not raw_text.strip():
        raise ValueError("No text to parse")

    logger.info(f"[MD_PARSER] Parsing {len(raw_text)} chars")

    sections = []
    tables = []
    current_heading = ""
    current_level = 1
    current_lines = []
    in_code = False

    for line in raw_text.split("\n"):
        if line.strip().startswith("```"):
            in_code = not in_code
            current_lines.append(line)
            continue

        if in_code:
            current_lines.append(line)
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if heading_match:
            if current_lines:
                content = "\n".join(current_lines).strip()
                if content and len(content) > 5:
                    if _is_table(content):
                        tables.append(Table(content=content, page=1))
                    else:
                        sections.append(Section(heading=current_heading, content=content, level=current_level, page=1))
                current_lines = []
            current_level = len(heading_match.group(1))
            current_heading = heading_match.group(2).strip()
            continue

        current_lines.append(line)

    if current_lines:
        content = "\n".join(current_lines).strip()
        if content and len(content) > 5:
            if _is_table(content):
                tables.append(Table(content=content, page=1))
            else:
                sections.append(Section(heading=current_heading, content=content, level=current_level, page=1))

    return ParsedDocument(
        title=sections[0].heading if sections and sections[0].heading else "",
        sections=sections, tables=tables,
        metadata=loaded_data.get("metadata", {}),
        file_type="Markdown", category="document",
    )


def _is_table(text):
    lines = text.strip().split("\n")
    if len(lines) < 2: return False
    return sum(1 for l in lines if "|" in l) / len(lines) > 0.6