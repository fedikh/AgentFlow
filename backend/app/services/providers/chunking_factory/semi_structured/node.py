"""Tree-node — one tree element = one chunk.

Records are STANDALONE chunks (full field text, never merged with neighbour
summaries) carrying their collection § and record metadata; other nodes get
the classic tiny-leaf merging. Safety net: an oversized node (e.g. a record
with a 40k description) is split with its heading re-prefixed on every
piece — never one giant chunk."""
from ..base import text_of, mk_chunk
from . import tree_stream, split_oversized

_SAFETY_MAX = 6000   # no chunk should meaningfully exceed this (embedding quality)


def chunk(parsed, cfg):
    min_chars = cfg.p("min_chars", 120)
    chunks, idx = [], 0

    def emit(text, section=None, meta=None):
        nonlocal idx
        for piece in split_oversized(text, _SAFETY_MAX):
            c = mk_chunk(piece, 1, idx, "node", section=section)
            if meta:
                c["meta"] = meta
            chunks.append(c)
            idx += 1

    for e in tree_stream(parsed):
        m = e.get("metadata") or {}
        t = text_of(e)
        if not t:
            continue
        if m.get("is_record"):
            emit(t, section=m.get("collection"),
                 meta={k: m[k] for k in ("record_type", "record_id", "primary_key")
                       if m.get(k)})
        elif (chunks and not chunks[-1].get("meta")
                and len(chunks[-1]["content"]) < min_chars):
            chunks[-1]["content"] += "\n" + t        # merge tiny non-record leaves
        else:
            emit(t)
    for i, c in enumerate(chunks):
        c["chunk_index"] = i
    return chunks
