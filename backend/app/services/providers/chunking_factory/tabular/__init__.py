"""Tabular chunking strategies (csv, xlsx, xls) + shared row helpers."""


def table_elements(elements):
    return [e for e in elements if e.get("type") == "table"]


def headers_of(content):
    return content.get("headers") or [c.get("name") for c in (content.get("columns") or [])]


def row_values(r):
    return r.get("values") if isinstance(r, dict) and "values" in r else r


import re as _re_hdr

_GENERIC_HDR = _re_hdr.compile(r"^(col|column)\s*_?\d+$|^unnamed", _re_hdr.I)


def pseudo_header_row(vals: dict) -> bool:
    """Excel styling artifact: a row whose values are 'Column1', 'Column2'…"""
    non_empty = [str(v).strip() for v in (vals or {}).values() if v not in (None, "", " ")]
    return bool(non_empty) and all(_re_hdr.fullmatch(r"Column\s*\d+", v) for v in non_empty)


def row_line(headers, vals, include_header=True):
    """One row as text. Empty cells are skipped; generic colN/Unnamed headers
    never label a value. include_header controls whether real COLUMN NAMES
    are written into the line (the 'Prefix header context' toggle):
        ON  → "question: How…? | answer: To…"   (row self-describing)
        OFF → "How…? | To…"                      (values only, fewer tokens)"""
    items = ([(h, vals.get(h)) for h in headers] if headers
             else list((vals or {}).items()))
    parts = []
    for h, v in items:
        if v in (None, "", " "):
            continue
        if include_header and h and not _GENERIC_HDR.match(str(h)):
            parts.append(f"{h}: {v}")
        else:
            parts.append(str(v))
    return " | ".join(parts)


import re as _re

_UUIDISH = _re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$|^[0-9a-f]{16,}$",
    _re.IGNORECASE)


def meaningful_name(content) -> str:
    """The table's display name, or '' when it is machine noise. Files are
    stored on disk as <document-uuid>.csv, so the parsed table_name is often
    a uuid — embedding that in every chunk is pure token noise."""
    name = (content.get("table_name") or content.get("caption") or "").strip()
    if not name or name.lower() == "table" or _UUIDISH.match(name):
        return ""
    return name


def chunk_prefix(content, location) -> str:
    """Context line for a row chunk: only MEANINGFUL parts (a real table name,
    an Excel sheet name). Empty when nothing meaningful exists — a lone CSV
    table needs no announcement."""
    parts = []
    name = meaningful_name(content)
    if name:
        parts.append(f"Table: {name}")
    sheet = (location or {}).get("sheet")
    if (sheet and str(sheet).strip() and not _UUIDISH.match(str(sheet))
            and str(sheet).strip().lower() != name.lower()):   # 'Table: X · Sheet: X' → once
        parts.append(f"Sheet: {sheet}")
    return " · ".join(parts)
