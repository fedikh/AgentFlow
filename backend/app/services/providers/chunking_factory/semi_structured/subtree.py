"""Subtree — a parent node plus its descendants packed into one chunk up to
max_chars, so a logical record (an object and its fields) stays together. A
subtree that overflows emits the node's own text, then recurses into children."""
from ..base import elements_of, text_of, order_of, mk_chunk


def _parent(e):
    return e.get("parent_id") or (e.get("relationships") or {}).get("parent")


def chunk(parsed, cfg):
    max_chars = cfg.p("max_chars", 1200)
    els = elements_of(parsed)
    if not els:
        return []

    by_id = {e.get("id"): e for e in els}
    kids, roots = {}, []
    for e in els:
        pid = _parent(e)
        if pid and pid in by_id:
            kids.setdefault(pid, []).append(e)
        else:
            roots.append(e)
    for lst in kids.values():
        lst.sort(key=order_of)
    roots.sort(key=order_of)

    def subtree_text(e):
        parts = [text_of(e)]
        for c in kids.get(e.get("id"), []):
            parts.append(subtree_text(c))
        return "\n".join(p for p in parts if p)

    chunks = [0]  # idx holder

    def emit(text, out):
        text = (text or "").strip()
        if text:
            out.append(mk_chunk(text, 1, chunks[0], "subtree")); chunks[0] += 1

    out = []

    def walk(e):
        st = subtree_text(e)
        if len(st) <= max_chars or not kids.get(e.get("id")):
            emit(st, out)
        else:
            emit(text_of(e), out)          # node summary, then split children
            for c in kids.get(e.get("id"), []):
                walk(c)

    for r in roots:
        walk(r)
    return out
