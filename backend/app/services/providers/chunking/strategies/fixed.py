"""Fixed-size chunking (with overlap) — RecursiveCharacterTextSplitter.

The RAG baseline: split every N characters, keeping an overlap so context
carries across boundaries. Section titles are detected and prefixed.
"""
from ..base import iterate_blocks, detect_section_title


def chunk(blocks, opts):
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=opts.chunk_size,
        chunk_overlap=opts.chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    strat = opts.strategy or "FIXED"

    def split_text(text):
        if not text:
            return []
        title = detect_section_title(text)
        pieces = [text] if len(text) <= opts.chunk_size else splitter.split_text(text)
        if title:
            pieces = [p if title in p else f"[Section: {title}]\n{p}" for p in pieces]
        return pieces

    return iterate_blocks(blocks, split_text, strat)
