"""
XML Loader — validates the file (lxml) and produces a readable text preview.

Structural (tree) parsing into the element schema happens in the Parse step
(xml_parser), so the lifecycle stays UPLOAD → LOADED → (Parse) → EXTRACTED and
the manual "Parse" button is preserved.
"""
import os
import logging

logger = logging.getLogger(__name__)


def load(file_path: str) -> dict:
    logger.info(f"[XML_LOADER] Loading: {os.path.basename(file_path)}")

    from lxml import etree
    from app.services.providers.loaders._utils import clean_text, build_doc_metadata

    try:
        tree = etree.parse(file_path, etree.XMLParser(recover=True))
        root = tree.getroot()
    except Exception as e:
        raise ValueError(f"Invalid XML file: {e}")
    if root is None:
        raise ValueError("Invalid XML file (no root element)")

    raw_text = clean_text(_xml_to_text(root))
    metadata = build_doc_metadata(file_path, 1, "xml", parser_name="lxml")

    return {
        "raw_text": raw_text,
        "num_pages": 1,
        "file_type": "XML",
        "category": "document",
        "metadata": metadata,
        "total_chars": len(raw_text),
    }


def _xml_to_text(element, depth: int = 0) -> str:
    """Indented, human-readable rendering of the tree (for the Loaded view)."""
    if not isinstance(element.tag, str):     # comment / processing instruction
        return ""
    tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag
    attrs = ""
    if element.attrib:
        attrs = " (" + ", ".join(f"{k}={v}" for k, v in element.attrib.items()) + ")"
    text = (element.text or "").strip()
    indent = "  " * depth
    lines = []
    if text and len(element) == 0:
        lines.append(f"{indent}{tag}{attrs}: {text}")
    else:
        lines.append(f"{indent}{tag}{attrs}:")
        if text:
            lines.append(f"{indent}  {text}")
    for child in element:
        sub = _xml_to_text(child, depth + 1)
        if sub:
            lines.append(sub)
    return "\n".join(lines)
