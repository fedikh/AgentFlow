"""Page-based chunking — one chunk per page (text + tables of that page merged).
Images stay as their own chunks. Useful for scanned PDFs and slide decks.
"""
from collections import OrderedDict
from ..base import mk_chunk, image_chunk


def chunk(blocks, opts):
    strat = opts.strategy or "PAGE"
    pages, images = OrderedDict(), []
    for b in blocks:
        if b.get("type") == "image":
            images.append(b)
            continue
        content = b.get("content", "")
        if b.get("type") == "table":
            content = f"[TABLE]\n{content}"
        pages.setdefault(b.get("page", 1), []).append(content)

    chunks = []
    for pg, parts in pages.items():
        text = "\n\n".join(p for p in parts if p and p.strip()).strip()
        if text:
            chunks.append(mk_chunk(text, pg, 0, strat))
    for b in images:
        chunks.append(image_chunk(b, 0, strat))

    chunks.sort(key=lambda c: c["page"])
    for i, c in enumerate(chunks):
        c["chunk_index"] = i
    return chunks
