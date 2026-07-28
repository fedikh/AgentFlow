"""Semi-structured chunking strategies (json, xml).

tree_stream() is the shared, DEDUPLICATED element stream every strategy
consumes:

  · a RECORD element carries its full searchable field text, so its
    descendants are EXCLUDED (otherwise every field would appear twice —
    once in the record text, once as its own leaf);
  · everything else (leaves, container summaries, out-of-collection keys)
    passes through untouched.

This guarantees: one piece of information appears in exactly ONE element,
whatever strategy runs on top.
"""
from ..base import elements_of, order_of


def tree_stream(parsed) -> list:
    els = elements_of(parsed)
    if not els:
        return []
    by_id = {e.get("id"): e for e in els}
    covered = set()

    def mark(eid):
        for k in (by_id.get(eid, {}).get("relationships", {}) or {}).get("children", []):
            covered.add(k)
            mark(k)

    for e in els:
        if (e.get("metadata") or {}).get("is_record"):
            mark(e.get("id"))
    return sorted((e for e in els if e.get("id") not in covered), key=order_of)


def split_oversized(text: str, max_chars: int) -> list:
    """A record bigger than max_chars is recursively split — and the record's
    HEADING (first line, e.g. 'Book bk101') is re-prefixed on every piece so
    no fragment loses its identity (LlamaIndex NodeParser behaviour)."""
    from ..base import split_recursive
    text = (text or "").strip()
    if len(text) <= max_chars:
        return [text] if text else []
    head, _, body = text.partition("\n")
    pieces = split_recursive(body or text, max_chars, 60)
    return [f"{head}\n{p}" if head and not p.startswith(head) else p
            for p in (x.strip() for x in pieces) if p]
