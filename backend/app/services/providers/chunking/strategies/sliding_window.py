"""Sliding-window chunking — a fixed window that advances with heavy overlap
(defaults to ~50%). Similar to fixed+overlap but with more redundancy so no
boundary information is lost.
"""
from ..base import iterate_blocks


def chunk(blocks, opts):
    size = max(1, opts.chunk_size)
    overlap = opts.chunk_overlap if opts.chunk_overlap else size // 2
    overlap = min(max(overlap, size // 2), size - 1)
    strat = opts.strategy or "SLIDING_WINDOW"

    from langchain_text_splitters import RecursiveCharacterTextSplitter
    sp = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    def split_text(text):
        if not text:
            return []
        if len(text) <= size:
            return [text]
        return sp.split_text(text)

    return iterate_blocks(blocks, split_text, strat)
