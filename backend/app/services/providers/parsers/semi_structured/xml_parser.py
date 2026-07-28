"""
XML Parser — builds the tree element schema (xml_element nodes) with lxml.
See parsers.tree_elements.build_xml_elements.
"""
import os
import logging
from app.services.providers.parsers.parsed_document import ParsedDocument, Section

logger = logging.getLogger(__name__)


def parse(loaded_data: dict) -> ParsedDocument:
    from lxml import etree

    fp = loaded_data.get("file_path")
    if fp and os.path.exists(fp):
        root = etree.parse(fp, etree.XMLParser(recover=True)).getroot()
    else:
        raw = loaded_data.get("raw_text", "")
        if not raw.strip():
            raise ValueError("No XML data to parse")
        # raw_text is the readable preview, not raw XML → needs the original file
        root = etree.fromstring(raw.encode("utf-8"), etree.XMLParser(recover=True))
    if root is None:
        raise ValueError("Could not parse XML (no root element)")

    logger.info("[XML_PARSER] Building tree elements")

    meta = dict(loaded_data.get("metadata", {}))
    from app.services.providers.parsers.tree_elements import build_xml_elements
    elements, root_name, text_repr = build_xml_elements(root, source=meta.get("source"))

    meta.update({"root": root_name, "encoding": "utf-8", "source_type": "xml"})

    # One section per detected RECORD ("Book bk101" + its fields) — the
    # enterprise shape. Only documents without repeated structures fall back
    # to the flattened single section.
    from app.services.providers.parsers.tree_elements import record_sections
    recs = record_sections(elements)
    if recs:
        sections = [Section(heading=r["heading"], content=r["content"],
                            level=r["level"], page=1) for r in recs]
    else:
        sections = [Section(heading=root_name or "", content=text_repr, level=1, page=1)]

    return ParsedDocument(
        title=root_name or "", sections=sections, elements=elements,
        metadata=meta, num_pages=1, file_type="XML", category="structured_data",
    )
