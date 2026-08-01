"""
Context Construction — turn the re-ranked chunks into the LLM's context.

    1. Select final chunks    — top_k best, within the token budget
    2. Remove duplicates      — same doc/page with near-identical text
    3. Merge overlapping      — adjacent chunk_index of the same document
                                stitch into one passage
    4. Preserve document order— the final context reads in document order
                                (doc → page → position), not score order
    5. Respect token budget   — hard cap (≈ 4 chars per token)

Every item carries document name, page, chunk ids, score and the search
method(s) that found it — citations stay traceable.
"""
from __future__ import annotations

import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)


def _doc_names(session_factory, doc_ids) -> dict:
    if not doc_ids:
        return {}
    db = session_factory()
    try:
        rows = db.execute(
            text("SELECT id, file_name FROM documents WHERE id = ANY(:ids)"),
            {"ids": list(doc_ids)},
        ).fetchall()
        return {r.id: r.file_name for r in rows}
    finally:
        db.close()


def build_context(cfg, session_factory, space, ranked: list) -> dict:
    budget = int(cfg.context_token_budget) * 4          # ≈ chars

    # 1+2) select the final chunks in rank order, skipping near-duplicates,
    #      within the token budget
    seen_sig, selected, used = set(), [], 0
    for c in ranked:
        sig = (c.document_id, c.page, (c.content or "")[:120])
        if sig in seen_sig:
            continue
        cost = len(c.content or "") + 80
        if used + cost > budget and selected:
            break
        seen_sig.add(sig)
        selected.append(c)
        used += cost
        if len(selected) >= cfg.top_k:
            break

    # 3+4) document order, then merge overlapping/adjacent chunks of the
    #      same document into one passage
    selected.sort(key=lambda c: (c.document_id, c.page, c.chunk_index))
    items, cur = [], None
    for c in selected:
        if (cur and c.document_id == cur["document_id"]
                and 0 <= c.chunk_index - cur["last_index"] <= 1
                and c.chunk_type == "text"):
            cur["content"] += "\n" + (c.content or "")
            cur["last_index"] = c.chunk_index
            cur["chunk_ids"].append(c.chunk_id)
            cur["score"] = max(cur["score"], c.score)
            cur["methods"] |= set(c.methods or {c.method})
        else:
            if cur:
                items.append(cur)
            cur = {
                "document_id": c.document_id, "page": c.page,
                "chunk_ids": [c.chunk_id], "last_index": c.chunk_index,
                "content": c.content or "", "score": c.score,
                "methods": set(c.methods or {c.method}),
                "chunk_type": c.chunk_type, "image_path": c.image_path,
            }
    if cur:
        items.append(cur)

    # 5) resolve document names + final shape
    names = _doc_names(session_factory, {m["document_id"] for m in items})
    out = [{
        "document": names.get(m["document_id"], "Unknown"),
        "document_id": m["document_id"],
        "page": m["page"],
        "chunk_id": m["chunk_ids"][0],
        "chunk_ids": m["chunk_ids"],
        "score": m["score"],
        "method": "+".join(sorted(m["methods"])),
        "content": m["content"],
        "chunk_type": m.get("chunk_type") or "text",
        "image_path": m.get("image_path"),
    } for m in items]
    return {"items": out, "chars": used}
