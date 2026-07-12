"""Character-based chunking — hard split every N characters (with overlap).

Simplest possible splitter; less accurate than fixed/recursive because it can
cut mid-word, but fully deterministic.
"""
from ..base import iterate_blocks


def chunk(blocks, opts):
    size = max(1, opts.chunk_size)
    overlap = min(max(0, opts.chunk_overlap), size - 1)
    strat = opts.strategy or "CHARACTER"

    def split_text(text):
        if not text:
            return []
        if len(text) <= size:
            return [text]
        out, start = [], 0
        while start < len(text):
            out.append(text[start:start + size])
            if start + size >= len(text):
                break
            start += size - overlap
        return out

    return iterate_blocks(blocks, split_text, strat)
