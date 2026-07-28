"""Record-based chunking — one chunk per detected BUSINESS RECORD.

Enterprise JSON/XML is usually a collection of repeated objects
(book/book/…, employee/employee/…, invoice/invoice/…). The parser detects
those and writes, on each record element:
    · searchable text  ("Book bk101 \\n Author: … \\n Title: …")
    · metadata         (record_type, record_id, collection, fields)

This strategy emits exactly one chunk per record — one embedding = one
logical object, which makes retrieval nearly perfect for entity questions.
Content outside the collections (headers, config keys) becomes one intro
chunk. Documents with no repeated structures fall back to Tree node."""
from ..base import elements_of, mk_chunk, text_of
from . import split_oversized


def chunk(parsed, cfg):
    max_chars = cfg.p("max_chars", 2500)
    els = elements_of(parsed)
    records = [e for e in els if (e.get("metadata") or {}).get("is_record")]
    if not records:
        from .node import chunk as node_chunk      # no repeated objects → tree node
        return node_chunk(parsed, cfg)

    by_id = {e["id"]: e for e in els}
    covered = set()          # DESCENDANTS of records (not the records themselves)

    def mark(eid):
        for k in (by_id.get(eid, {}).get("relationships", {}) or {}).get("children", []):
            covered.add(k)
            mark(k)

    for r in records:
        mark(r["id"])

    # NESTED collections (orders → items): keep only the OUTERMOST records —
    # a nested record is a descendant of its parent record (∈ covered) and its
    # fields already live inside the parent's text ("Items > sku: A1").
    # Emitting both would duplicate every nested field.
    records = [r for r in records if r["id"] not in covered]

    chunks, idx = [], 0

    # context outside any record (root config, headers) → one intro chunk
    extra = []
    for e in els:
        if e["id"] in covered or (e.get("metadata") or {}).get("is_collection"):
            continue
        c = e.get("content") or {}
        t = c.get("normalized_text") or ""
        if not t and c.get("json_type") not in (None, "object", "array"):
            v = c.get("value")
            if v not in (None, ""):
                key = c.get("key")
                t = f"{key}: {v}" if key else str(v)
        if t:
            extra.append(t)
    if extra:
        chunks.append(mk_chunk("\n".join(extra)[:max_chars], 1, idx, "record",
                               section="document"))
        idx += 1

    for r in records:
        meta = r.get("metadata") or {}
        text = text_of(r)
        if not text:
            continue
        pieces = split_oversized(text, max_chars)
        for p in pieces:
            ch = mk_chunk(p, 1, idx, "record", section=meta.get("collection") or None)
            ch["meta"] = {k: v for k, v in {
                "record_type": meta.get("record_type"),
                "record_id": meta.get("record_id"),
                "primary_key": meta.get("primary_key"),
                "keywords": meta.get("keywords") or None,
                "fields": meta.get("fields") or None,
            }.items() if v}
            chunks.append(ch)
            idx += 1
    return chunks
