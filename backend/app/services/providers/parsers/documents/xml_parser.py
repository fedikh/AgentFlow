"""
XML Parser — converts XML structure to ParsedDocument.

Strategy:
  - Each element with text → Section (tag as heading)
  - Repeated sibling elements with same structure → Table
  - Attributes included in section content
"""
import logging
import xml.etree.ElementTree as ET
from app.services.providers.parsers.parsed_document import ParsedDocument, Section, Table

logger = logging.getLogger(__name__)


def parse(loaded_data: dict) -> ParsedDocument:
    raw_text = loaded_data.get("raw_text", "")
    file_path = loaded_data.get("file_path")

    if not raw_text and not file_path:
        raise ValueError("No XML data to parse")

    logger.info(f"[XML_PARSER] Parsing")

    # Parse XML
    if file_path:
        tree = ET.parse(file_path)
        root = tree.getroot()
    else:
        # Reconstruct XML from raw_text — need original file
        # raw_text is already converted to readable format by loader
        # Try to find original XML
        raise ValueError("XML parser needs the original file (file_path)")

    sections = []
    tables = []

    # Check for repeated children (table pattern)
    child_tags = [_clean_tag(c.tag) for c in root]
    tag_counts = {}
    for t in child_tags:
        tag_counts[t] = tag_counts.get(t, 0) + 1

    # Process children
    for tag, count in tag_counts.items():
        children = [c for c in root if _clean_tag(c.tag) == tag]

        if count >= 3 and _is_table_pattern(children):
            # Repeated elements with same structure → Table
            _extract_table(children, tag, tables)
        else:
            # Individual elements → Sections
            for child in children:
                _extract_sections(child, sections, level=1, prefix="")

    # If root has direct text
    root_text = (root.text or "").strip()
    if root_text and len(root_text) > 5:
        sections.insert(0, Section(heading=_clean_tag(root.tag), content=root_text, level=1, page=1))

    title = _clean_tag(root.tag)

    return ParsedDocument(
        title=title,
        sections=sections,
        tables=tables,
        metadata=loaded_data.get("metadata", {}),
        file_type="XML",
        category="document",
    )


def _extract_sections(element, sections: list, level: int, prefix: str):
    """Recursively extract sections from XML element."""
    tag = _clean_tag(element.tag)
    heading = f"{prefix} > {tag}" if prefix else tag

    # Collect text
    text_parts = []
    if (element.text or "").strip():
        text_parts.append(element.text.strip())

    # Attributes as metadata
    if element.attrib:
        attrs = ", ".join(f"{k}: {v}" for k, v in element.attrib.items())
        text_parts.append(f"[{attrs}]")

    # If leaf node (no children)
    if not list(element):
        if text_parts:
            sections.append(Section(
                heading=heading,
                content="\n".join(text_parts),
                level=min(level, 4),
                page=1,
            ))
        return

    # Has children — add this element's text first
    if text_parts:
        sections.append(Section(
            heading=heading,
            content="\n".join(text_parts),
            level=min(level, 4),
            page=1,
        ))

    # Recurse into children
    for child in element:
        _extract_sections(child, sections, level + 1, heading)


def _extract_table(children: list, tag: str, tables: list):
    """Convert repeated XML elements into a Table."""
    # Get all unique keys from children
    all_keys = []
    for child in children:
        for sub in child:
            key = _clean_tag(sub.tag)
            if key not in all_keys:
                all_keys.append(key)

    # Also include attributes as columns
    attr_keys = []
    for child in children:
        for k in child.attrib:
            if k not in attr_keys:
                attr_keys.append(k)

    headers = attr_keys + all_keys

    # Build rows
    rows = []
    for child in children:
        row = []
        for k in attr_keys:
            row.append(child.attrib.get(k, ""))
        for k in all_keys:
            sub = child.find(k) if "}" not in k else None
            if sub is None:
                # Try with namespace
                for s in child:
                    if _clean_tag(s.tag) == k:
                        sub = s
                        break
            row.append((sub.text or "").strip() if sub is not None else "")
        rows.append(row)

    # Markdown
    md = ["| " + " | ".join(str(h) for h in headers) + " |"]
    md.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        md.append("| " + " | ".join(str(v) for v in row) + " |")

    tables.append(Table(
        content=f"[{tag}]\n" + "\n".join(md),
        headers=headers,
        rows=rows,
        num_rows=len(rows),
        num_cols=len(headers),
        page=1,
    ))


def _is_table_pattern(children: list) -> bool:
    """Check if children have similar structure (same sub-elements)."""
    if not children:
        return False
    first_keys = set(_clean_tag(c.tag) for c in children[0])
    if not first_keys:
        return False
    for child in children[1:]:
        keys = set(_clean_tag(c.tag) for c in child)
        if keys != first_keys:
            return False
    return True


def _clean_tag(tag: str) -> str:
    """Remove namespace from XML tag."""
    if "}" in tag:
        return tag.split("}")[-1]
    return tag