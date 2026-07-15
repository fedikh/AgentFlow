"""Row-batch — N rows per chunk (header prefixed once). Fewer, coarser chunks."""
from ..base import elements_of, mk_chunk
from . import table_elements, headers_of, row_values, row_line


def chunk(parsed, cfg):
    n = max(1, int(cfg.p("rows_per_chunk", 20)))
    include_header = cfg.p("include_header", True)
    chunks, idx = [], 0

    for tbl in table_elements(elements_of(parsed)):
        c = tbl.get("content") or {}
        loc = tbl.get("location") or {}
        headers = headers_of(c)
        name = c.get("table_name") or "Table"
        sheet = loc.get("sheet")
        prefix = f"Table: {name}" + (f" (sheet {sheet})" if sheet else "")

        lines = []
        for r in (c.get("rows") or []):
            vals = row_values(r)
            if isinstance(vals, dict):
                ln = row_line(headers, vals)
                if ln.strip():
                    lines.append(ln)

        for i in range(0, len(lines), n):
            batch = lines[i:i + n]
            body = "\n".join(batch)
            content = f"{prefix}\n{body}" if include_header else body
            chunks.append(mk_chunk(content, 1, idx, "row_batch")); idx += 1
    return chunks
