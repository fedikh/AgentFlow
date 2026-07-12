"""
HTML Parser (web) — builds the canonical element model from HTML via
web_elements.build_web_elements (BeautifulSoup). Produces heading / paragraph /
list_item / table / code / image / quote elements, plus document-level images
and links.
"""
import os
import logging
from app.services.providers.parsers.parsed_document import ParsedDocument, Section

logger = logging.getLogger(__name__)


def parse(loaded_data: dict) -> ParsedDocument:
    html = loaded_data.get("html")
    fp = loaded_data.get("file_path")
    if not html and fp and os.path.exists(fp):
        with open(fp, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()
    if not html:
        html = loaded_data.get("raw_text", "")
    if not html or not html.strip():
        raise ValueError("No HTML content to parse")

    logger.info("[HTML_PARSER] Building canonical web elements")

    meta_in = loaded_data.get("metadata", {})
    base_url = meta_in.get("source_url") or meta_in.get("canonical_url")

    from app.services.providers.parsers.web_elements import build_web_elements
    from app.services.providers.parsers.hierarchy import build_hierarchy
    elements, images, links, meta_extra, text_repr = build_web_elements(html, base_url)
    build_hierarchy(elements, infer_levels=False)   # h1-h6 levels are authoritative

    meta = dict(meta_in)
    meta.update({k: v for k, v in meta_extra.items() if v})
    meta["source_type"] = "web"
    meta["links"] = links
    meta["parser"] = meta_in.get("engine", "beautifulsoup")

    sections = [Section(heading="", content=text_repr, level=1, page=1)] if text_repr.strip() else []

    return ParsedDocument(
        title=meta.get("title") or "", sections=sections, elements=elements,
        images=images, metadata=meta, num_pages=1, file_type="HTML", category="web",
    )
