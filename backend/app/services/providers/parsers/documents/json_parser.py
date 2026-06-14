"""
JSON Parser — converts JSON structure to ParsedDocument.

Strategy:
  - dict → each top-level key becomes a Section
  - list of objects → becomes a Table (headers from keys, rows from values)
  - nested dicts → flattened into sections with heading = key path
"""
import json
import logging
from app.services.providers.parsers.parsed_document import ParsedDocument, Section, Table

logger = logging.getLogger(__name__)


def parse(loaded_data: dict) -> ParsedDocument:
    raw_text = loaded_data.get("raw_text", "")
    if not raw_text.strip():
        raise ValueError("No JSON data to parse")

    logger.info(f"[JSON_PARSER] Parsing {len(raw_text)} chars")

    data = json.loads(raw_text)

    sections = []
    tables = []

    if isinstance(data, list):
        # List of items
        if data and isinstance(data[0], dict):
            # List of objects → Table
            headers = list(data[0].keys())
            rows = []
            for item in data:
                rows.append([item.get(h, "") for h in headers])

            # Markdown
            md = ["| " + " | ".join(str(h) for h in headers) + " |"]
            md.append("| " + " | ".join("---" for _ in headers) + " |")
            for row in rows:
                md.append("| " + " | ".join(str(v) for v in row) + " |")

            tables.append(Table(
                content="\n".join(md),
                headers=headers,
                rows=rows,
                num_rows=len(rows),
                num_cols=len(headers),
                page=1,
            ))
        else:
            # List of simple values
            content = "\n".join(f"- {item}" for item in data)
            sections.append(Section(heading="Items", content=content, level=1, page=1))

    elif isinstance(data, dict):
        # Dict → each key becomes a section
        _parse_dict(data, sections, tables, prefix="", level=1)

    else:
        # Simple value
        sections.append(Section(heading="", content=str(data), level=1, page=1))

    return ParsedDocument(
        title=loaded_data.get("metadata", {}).get("source", ""),
        sections=sections,
        tables=tables,
        metadata=loaded_data.get("metadata", {}),
        file_type="JSON",
        category="document",
    )


def _parse_dict(data: dict, sections: list, tables: list, prefix: str, level: int):
    """Recursively parse a dict into sections and tables."""
    for key, value in data.items():
        heading = f"{prefix}{key}" if not prefix else f"{prefix} > {key}"

        if isinstance(value, dict):
            # Nested dict → recurse
            _parse_dict(value, sections, tables, heading, level + 1)

        elif isinstance(value, list):
            if value and isinstance(value[0], dict):
                # List of objects → Table
                headers = list(value[0].keys())
                rows = [[item.get(h, "") for h in headers] for item in value]

                md = ["| " + " | ".join(str(h) for h in headers) + " |"]
                md.append("| " + " | ".join("---" for _ in headers) + " |")
                for row in rows:
                    md.append("| " + " | ".join(str(v) for v in row) + " |")

                tables.append(Table(
                    content=f"[{heading}]\n" + "\n".join(md),
                    headers=headers,
                    rows=rows,
                    num_rows=len(rows),
                    num_cols=len(headers),
                    page=1,
                ))
            else:
                # List of simple values
                content = "\n".join(f"- {item}" for item in value)
                sections.append(Section(heading=heading, content=content, level=level, page=1))

        else:
            # Simple value → section
            sections.append(Section(heading=heading, content=str(value), level=level, page=1))