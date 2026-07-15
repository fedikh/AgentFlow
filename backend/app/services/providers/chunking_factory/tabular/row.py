"""Row-based — one row (+ header context) = one clean, citable chunk."""
from ..base import elements_of, mk_chunk, text_of
from . import table_elements, headers_of, row_values, row_line


def chunk(parsed, cfg):
    include_header = cfg.p("include_header", True)
    els = elements_of(parsed)
    tables = table_elements(els)
    chunks, idx = [], 0

    if not tables:                       # no structured table → fall back to text
        for e in els:
            t = text_of(e)
            if t:
                chunks.append(mk_chunk(t, 1, idx, "row")); idx += 1
        return chunks

    for tbl in tables:
        c = tbl.get("content") or {}
        loc = tbl.get("location") or {}
        headers = headers_of(c)
        name = c.get("table_name") or "Table"
        sheet = loc.get("sheet")
        prefix = f"Table: {name}" + (f" (sheet {sheet})" if sheet else "")
        for r in (c.get("rows") or []):
            vals = row_values(r)
            if not isinstance(vals, dict):
                continue
            line = row_line(headers, vals)
            if not line.strip():
                continue
            content = f"{prefix}\n{line}" if include_header else line
            chunks.append(mk_chunk(content, 1, idx, "row")); idx += 1
    return chunks
