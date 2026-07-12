"""
Hierarchy builder — infers real heading levels and parent links.

Docling (and most parsers) often label every heading as level 1, which flattens
the document tree. This module reconstructs nesting from the heading *numbering*:

    "2. Périmètre Fonctionnel"   → level 1
    "2.1 Gestion Multi-tenant"   → level 2   parent = "2. Périmètre Fonctionnel"
    "2.2.1 Configuration"        → level 3   parent = "2.2 Module Agent IA"

When a heading has no numbering, the parser's own level is kept as a fallback.
Two appliers are provided:
    build_hierarchy(elements)          → the new element schema (dicts)
    build_section_hierarchy(sections)  → the legacy Section objects
"""
import re

# "2", "2.1", "2.2.1", optionally followed by ')' or '.' then whitespace.
_NUM_HEADING = re.compile(r"^\s*(\d+(?:\.\d+)+|\d+)[.)]?\s+\S")


def heading_level(text: str, fallback: int = 1) -> int:
    """Infer a heading's depth from its leading section number, else `fallback`."""
    m = _NUM_HEADING.match(text or "")
    if m:
        return len(m.group(1).split("."))
    try:
        return max(1, int(fallback or 1))
    except Exception:
        return 1


def build_hierarchy(elements: list, infer_levels: bool = True) -> list:
    """
    Rebuild level + parent + parent_section on the element list (in place).

    * heading  → parent/parent_section point at the nearest enclosing heading
                 (lower level). When `infer_levels` is True the level is derived
                 from section numbering (PDF/DOCX/PPTX/text, which have no
                 explicit level); when False the element's existing level is
                 trusted (Markdown, whose `#` count is authoritative).
    * other    → parent/parent_section point at the heading it lives under.
    """
    stack = []  # list of (level, heading_element)
    for el in elements:
        if not isinstance(el, dict):
            continue
        hy = el.setdefault("hierarchy", {})
        if el.get("type") == "heading":
            text = (el.get("content") or {}).get("text", "")
            lvl = (heading_level(text, el.get("level", 1))
                   if infer_levels else (el.get("level", 1) or 1))
            el["level"] = lvl
            while stack and stack[-1][0] >= lvl:
                stack.pop()
            parent = stack[-1][1] if stack else None
            hy["parent"] = parent["id"] if parent else None
            hy["parent_section"] = (parent.get("content") or {}).get("text") if parent else None
            stack.append((lvl, el))
        else:
            parent = stack[-1][1] if stack else None
            hy["parent"] = parent["id"] if parent else None
            hy["parent_section"] = (parent.get("content") or {}).get("text") if parent else None
    return elements


def build_section_hierarchy(sections: list) -> list:
    """Set level + parent_section on the legacy Section objects (in place)."""
    stack = []  # list of (level, heading_text)
    for sec in sections:
        heading = (getattr(sec, "heading", "") or "").strip()
        if not heading:
            # Content-only section: inherit the current parent, don't nest under it.
            sec.parent_section = stack[-1][1] if stack else None
            continue
        lvl = heading_level(heading, getattr(sec, "level", 1))
        sec.level = lvl
        while stack and stack[-1][0] >= lvl:
            stack.pop()
        sec.parent_section = stack[-1][1] if stack else None
        stack.append((lvl, heading))
    return sections
