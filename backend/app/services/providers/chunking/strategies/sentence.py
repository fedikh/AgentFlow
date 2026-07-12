"""Sentence-based chunking — LlamaIndex SentenceSplitter (respects sentence
boundaries, token-aware). Good for articles, books and documentation.

Falls back to a regex sentence packer if llama-index isn't available.
"""
import re
from ..base import iterate_blocks

_SENT = re.compile(r"(?<=[.!?])\s+")


def _fallback(text, size):
    sents = [s.strip() for s in _SENT.split(text.strip()) if s.strip()]
    out, cur = [], ""
    for s in sents:
        if cur and len(cur) + 1 + len(s) > size:
            out.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        out.append(cur)
    return out


def chunk(blocks, opts):
    strat = opts.strategy or "SENTENCE"
    splitter = None
    try:
        from llama_index.core.node_parser import SentenceSplitter
        splitter = SentenceSplitter(
            chunk_size=max(32, opts.chunk_size),
            chunk_overlap=min(max(0, opts.chunk_overlap), opts.chunk_size // 2),
        )
    except Exception:
        splitter = None

    def split_text(text):
        if not text:
            return []
        return splitter.split_text(text) if splitter else _fallback(text, opts.chunk_size)

    return iterate_blocks(blocks, split_text, strat)
