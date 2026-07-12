"""Document-structure chunking — each parser element (paragraph, table, image)
becomes its own chunk, with NO further splitting. Best used with Docling output
so titles, tables and figures stay as clean, self-contained units.
"""
from ..base import mk_chunk, table_chunk, image_chunk


def chunk(blocks, opts):
    strat = opts.strategy or "DOCUMENT_STRUCTURE"
    chunks, idx = [], 0
    for b in blocks:
        btype = b.get("type", "text")
        if btype == "table":
            chunks.append(table_chunk(b, idx, strat))
        elif btype == "image":
            chunks.append(image_chunk(b, idx, strat))
        else:
            txt = (b.get("content", "") or "").strip()
            if not txt:
                continue
            chunks.append(mk_chunk(txt, b.get("page", 1), idx, strat))
        idx += 1
    return chunks
