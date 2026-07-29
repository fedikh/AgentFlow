"""Row-batch — N rows per chunk (header prefixed once). Fewer, coarser chunks."""
from ..base import elements_of, mk_chunk
from . import (table_elements, headers_of, row_values, row_line,
               chunk_prefix, meaningful_name, pseudo_header_row)


def chunk(parsed, cfg):
    n = max(1, int(cfg.p("rows_per_chunk", 20)))
    include_header = cfg.p("include_header", True)
    chunks, idx = [], 0

    for tbl in table_elements(elements_of(parsed)):
        c = tbl.get("content") or {}
        loc = tbl.get("location") or {}
        headers = headers_of(c)
        prefix = chunk_prefix(c, loc)
        section = (loc.get("sheet") or meaningful_name(c) or None)

        lines = []
        for r in (c.get("rows") or []):
            vals = row_values(r)
            if isinstance(vals, dict) and not pseudo_header_row(vals):
                ln = row_line(headers, vals, include_header)
                if ln.strip():
                    lines.append(ln)

        for i in range(0, len(lines), n):
            batch = lines[i:i + n]
            body = "\n".join(batch)
            content = f"{prefix}\n{body}" if prefix else body
            chunks.append(mk_chunk(content, 1, idx, "row_batch")); idx += 1
    return chunks
