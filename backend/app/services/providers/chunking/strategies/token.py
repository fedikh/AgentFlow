"""Token-based chunking — LlamaIndex TokenTextSplitter (tokenizer-aligned).

`chunk_size` / `chunk_overlap` are token counts. Falls back to fixed if
llama-index isn't available.
"""
from ..base import iterate_blocks


def chunk(blocks, opts):
    strat = opts.strategy or "TOKEN"
    try:
        from llama_index.core.node_parser import TokenTextSplitter
        sp = TokenTextSplitter(
            chunk_size=max(16, opts.chunk_size),
            chunk_overlap=min(max(0, opts.chunk_overlap), opts.chunk_size // 2),
        )
    except Exception:
        from . import fixed
        return fixed.chunk(blocks, opts)

    def split_text(text):
        return sp.split_text(text) if text else []

    return iterate_blocks(blocks, split_text, strat)
