"""
XML Loader — reads XML files, converts to readable text.
"""
import os
import logging

logger = logging.getLogger(__name__)


def load(file_path: str) -> dict:
    logger.info(f"[XML_LOADER] Loading: {os.path.basename(file_path)}")

    import chardet

    with open(file_path, "rb") as f:
        raw = f.read()
    detected = chardet.detect(raw)
    encoding = detected.get("encoding", "utf-8") or "utf-8"
    content = raw.decode(encoding, errors="replace")

    # Validate XML
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML file: {e}")

    # Convert to readable text
    raw_text = _xml_to_text(root)

    # Metadata
    metadata = {
        "root_tag": root.tag,
        "num_children": len(list(root)),
        "encoding": encoding,
        "source": os.path.basename(file_path),
    }

    # Count all elements
    all_tags = set()
    for el in root.iter():
        all_tags.add(el.tag)
    metadata["tags"] = ", ".join(list(all_tags)[:20])
    metadata["num_tags"] = len(all_tags)

    from app.services.providers.loaders._utils import clean_text
    raw_text = clean_text(raw_text)

    return {
        "raw_text": raw_text,
        "num_pages": 1,
        "file_type": "XML",
        "category": "document",
        "metadata": metadata,
        "total_chars": len(raw_text),
    }


def _xml_to_text(element, depth=0) -> str:
    """Convert XML element tree to indented readable text."""
    lines = []
    tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag  # remove namespace

    # Attributes
    attrs = ""
    if element.attrib:
        attrs = " (" + ", ".join(f"{k}={v}" for k, v in element.attrib.items()) + ")"

    # Text content
    text = (element.text or "").strip()

    indent = "  " * depth

    if text and not list(element):
        # Leaf node with text
        lines.append(f"{indent}{tag}{attrs}: {text}")
    elif text:
        lines.append(f"{indent}{tag}{attrs}:")
        lines.append(f"{indent}  {text}")
    else:
        lines.append(f"{indent}{tag}{attrs}:")

    # Children
    for child in element:
        lines.append(_xml_to_text(child, depth + 1))

    # Tail text
    tail = (element.tail or "").strip()
    if tail:
        lines.append(f"{indent}{tail}")

    return "\n".join(lines)