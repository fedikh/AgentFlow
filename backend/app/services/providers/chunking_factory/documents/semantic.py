"""Semantic — uses embeddings (LlamaIndex SemanticSplitterNodeParser) to detect
where the MEANING changes, grouping related content and splitting on topic
shifts. Runs across the whole document (not per-section), so it can merge small
sections on the same topic and split a large section when the topic changes."""
from ..base import (document_stream, make_semantic_split, mk_chunk, elements_of,
                    _page_at)


def chunk(parsed, cfg):
    max_chars = cfg.p("max_chars", 1200)
    threshold = cfg.p("threshold", 75)
    text, offsets = document_stream(elements_of(parsed))
    if not text.strip():
        return []

    split_fn = make_semantic_split(max_chars, threshold)
    chunks, consumed, idx = [], 0, 0
    for piece in split_fn(text):
        piece = (piece or "").strip()
        if piece:
            chunks.append(mk_chunk(piece, _page_at(offsets, consumed), idx, "semantic"))
            idx += 1
        consumed += len(piece)
    return chunks
