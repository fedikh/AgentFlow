"""
HTML Parser (web) — builds the canonical element model from HTML via
web_elements.build_web_elements (BeautifulSoup). Produces heading / paragraph /
list_item / table / code / image / quote elements, plus document-level images
and links.
"""
import os
import logging
from app.services.providers.parsers.parsed_document import ParsedDocument, Section, Table

logger = logging.getLogger(__name__)


def _blocks_from_elements(elements):
    """Build the legacy sections/tables blocks from the web elements so the
    'Blocks' view renders web pages the same way as PDF/DOCX — split per heading,
    with tables as their own blocks — instead of one monolithic text dump."""
    sections, tables = [], []
    cur_heading, cur_level, cur_lines = "", 1, []

    def flush():
        nonlocal cur_lines, cur_heading, cur_level
        content = "\n".join(cur_lines).strip()
        if content or cur_heading:
            sections.append(Section(heading=cur_heading, content=content,
                                    level=cur_level or 1, page=1))
        cur_lines = []

    for el in (elements or []):
        t = el.get("type")
        c = el.get("content") or {}
        if t == "heading":
            flush()
            cur_heading = (c.get("text") or "").strip()
            cur_level = el.get("level") or 1
        elif t == "table":
            headers = c.get("headers") or []
            rows = c.get("rows") or []
            tables.append(Table(content=c.get("markdown") or "", headers=headers,
                                num_rows=len(rows), num_cols=len(headers), page=1))
        elif t in ("paragraph", "list_item", "code", "quote"):
            txt = (c.get("text") or "").strip()
            if txt:
                cur_lines.append(("• " + txt) if t == "list_item" else txt)
    flush()
    return sections, tables


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

    # Build per-heading blocks (like PDF) so the Blocks view isn't one big dump.
    sections, tables = _blocks_from_elements(elements)
    if not sections and text_repr.strip():   # fallback: page with no structure
        sections = [Section(heading="", content=text_repr, level=1, page=1)]

    return ParsedDocument(
        title=meta.get("title") or "", sections=sections, tables=tables,
        elements=elements, images=images, metadata=meta,
        num_pages=1, file_type="HTML", category="web",
    )
