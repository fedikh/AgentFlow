"""Semantic — uses embeddings (LlamaIndex SemanticSplitterNodeParser, with a
MULTILINGUAL sentence model) to detect where the MEANING changes, grouping
related content and splitting on topic shifts.

Runs through the shared structure-preserving driver (flatten_split), so the
semantic cutting happens INSIDE sections while the document structure stays
intact: a new section starts at each heading, the § breadcrumb is prepended
and recorded, tables stay whole as [TABLE] chunks, and images keep their own
image_summary chunks. (The old implementation flattened the whole document —
tables could be sliced in half and sections/breadcrumbs were lost.)"""
from ..base import flatten_split, make_semantic_split, elements_of, split_fixed


def chunk(parsed, cfg):
    max_chars = cfg.p("max_chars", 1200)
    threshold = cfg.p("threshold", 75)
    split_fn = make_semantic_split(max_chars, threshold)
    chunks = flatten_split(elements_of(parsed), split_fn, "semantic")
    return _size_cleanup(chunks, max_chars)


def _size_cleanup(chunks, max_chars, min_chars=150):
    """The semantic splitter can leave tiny tail fragments and (on text with
    no sentence boundaries, e.g. column lists) runaway segments. Merge the
    tiny ones into their neighbour; hard-split anything over 2x max."""
    out = []
    for c in chunks:
        content = (c.get("content") or "").strip()
        if not content:
            continue
        if c.get("type", "text") != "text":
            out.append(c)
            continue
        if len(content) > max_chars * 2:
            for piece in split_fixed(content, max_chars, 0):
                nc = dict(c)
                nc["content"] = piece
                out.append(nc)
            continue
        prev = out[-1] if out and out[-1].get("type", "text") == "text" else None
        if (len(content) < min_chars and prev is not None
                and prev.get("section") == c.get("section")
                and len(prev["content"]) + len(content) < int(max_chars * 1.3)):
            prev["content"] = prev["content"].rstrip() + "\n" + content
            continue
        out.append(c)
    for i, c in enumerate(out):
        c["chunk_index"] = i
    return out
