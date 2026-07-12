"""Row-based chunking — for tabular data (CSV/Excel). Each table row becomes a
chunk (with the header prepended for context). Free text is split per line.
"""
from ..base import mk_chunk, image_chunk


def chunk(blocks, opts):
    strat = opts.strategy or "ROW"
    chunks, idx = [], 0
    for b in blocks:
        btype = b.get("type", "text")
        page = b.get("page", 1)
        if btype == "image":
            chunks.append(image_chunk(b, idx, strat))
            idx += 1
            continue
        content = b.get("content", "") or ""
        if btype == "table":
            lines = [ln for ln in content.splitlines() if ln.strip()]
            header = lines[0] if lines else ""
            body = lines[1:] if len(lines) > 1 else lines
            for ln in body:
                txt = f"{header}\n{ln}" if header and header != ln else ln
                chunks.append(mk_chunk(txt, page, idx, strat, ctype="table"))
                idx += 1
        else:
            for ln in content.splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                chunks.append(mk_chunk(ln, page, idx, strat))
                idx += 1
    return chunks
