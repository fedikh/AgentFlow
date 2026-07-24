"""
Context Builder — turn the ranked chunks into the final, ordered LLM context.

    • duplicate removal (same doc/page near-identical text)
    • neighbour merge: adjacent chunk_index of the same document stitch into
      one passage (keeps sentences that chunking split apart)
    • parent attach: when a chunk has parent_index, the parent chunk of the
      same document is pulled in for fuller context (budget permitting)
    • token budget: hard cap on total context size (≈ 4 chars per token)
    • every item carries document name, page, chunk id, score and the
      retrieval method(s) that found it — citations stay traceable.
"""
from __future__ import annotations

import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)


def _doc_names(session_factory, doc_ids):
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


def _parents(session_factory, space_id, wanted):
    """wanted: set of (document_id, parent_index) → {key: content}"""
    if not wanted:
        return {}
    db = session_factory()
    try:
        out = {}
        for doc_id, pidx in list(wanted)[:20]:
            row = db.execute(
                text("""SELECT content FROM chunks
                        WHERE rag_space_id = :sid AND document_id = :d AND chunk_index = :i
                        LIMIT 1"""),
                {"sid": space_id, "d": doc_id, "i": pidx},
            ).fetchone()
            if row:
                out[(doc_id, pidx)] = row.content
        return out
    finally:
        db.close()


def _compress_light(text: str) -> str:
    """Built-in compression: collapse whitespace, drop repeated lines
    (headers/footers boilerplate) and blank-line runs. Cheap and safe."""
    seen, out = set(), []
    prev_blank = False
    for line in (text or "").splitlines():
        s = " ".join(line.split())
        if not s:
            if prev_blank:
                continue
            prev_blank = True
            out.append("")
            continue
        prev_blank = False
        key = s.lower()
        if key in seen and len(s) >= 8:      # repeated boilerplate line
            continue
        seen.add(key)
        out.append(s)
    return "\n".join(out).strip()


def _compress_llmlingua(text: str, target_tokens: int) -> str:
    """Optional LLMLingua/LongLLMLingua compression — used only if the package
    is installed; falls back to light compression otherwise."""
    try:
        from llmlingua import PromptCompressor
        global _LINGUA
        if "_LINGUA" not in globals() or _LINGUA is None:
            _LINGUA = PromptCompressor(
                model_name="microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
                use_llmlingua2=True,
            )
        res = _LINGUA.compress_prompt(text, target_token=target_tokens)
        return res.get("compressed_prompt") or text
    except Exception as e:
        logger.warning(f"[RETRIEVAL/compress] llmlingua unavailable ({e}) — light mode")
        return _compress_light(text)


def _auto_merge(cfg, session_factory, space, chunks: list) -> list:
    """AutoMerging: when ≥ N retrieved chunks share the same parent, replace
    them with the PARENT chunk itself — the section reads whole instead of as
    fragments (great for PDFs/tables split by hierarchical chunking)."""
    from collections import defaultdict
    groups = defaultdict(list)
    for c in chunks:
        if c.parent_index is not None:
            groups[(c.document_id, c.parent_index)].append(c)

    to_merge = {k: v for k, v in groups.items()
                if len(v) >= int(cfg.parent_merge_children)}
    if not to_merge:
        return chunks
    parents = _parents(session_factory, space.id, set(to_merge.keys()))

    out, merged_keys = [], set()
    for c in chunks:
        key = (c.document_id, c.parent_index)
        if key in to_merge and key in parents:
            if key in merged_keys:
                continue                       # siblings collapse into one
            merged_keys.add(key)
            best = max(to_merge[key], key=lambda x: x.score)
            best.content = parents[key]
            best.method = (best.method + "+automerge") if "automerge" not in best.method else best.method
            best.methods = set(best.methods or set()) | {"automerge"}
            out.append(best)
        else:
            out.append(c)
    return out


def build_context(cfg, session_factory, space, ranked: list) -> dict:
    budget = int(cfg.context_token_budget) * 4          # chars
    used = 0

    # 0) AutoMerging parent retrieval (before selection, so the merged parent
    #    competes at the fragment's rank)
    if getattr(cfg, "auto_merge_parents", False):
        try:
            ranked = _auto_merge(cfg, session_factory, space, ranked)
        except Exception as e:
            logger.warning(f"[RETRIEVAL/context] auto-merge failed: {e}")

    # 1) near-duplicate removal (fusion already deduped by id)
    seen_sig, picked = set(), []
    for c in ranked:
        sig = (c.document_id, c.page, (c.content or "")[:120])
        if sig in seen_sig:
            continue
        seen_sig.add(sig)
        picked.append(c)
        if len(picked) >= max(cfg.top_k * 3, 12):
            break

    # 2) budgeted selection in rank order
    selected = []
    for c in picked:
        cost = len(c.content or "") + 80
        if used + cost > budget and selected:
            break
        selected.append(c)
        used += cost
        if len(selected) >= cfg.top_k:
            break

    # 3) neighbour merge: same document + adjacent chunk_index → one passage
    items = []
    if cfg.merge_neighbors:
        selected_sorted = sorted(selected, key=lambda c: (c.document_id, c.chunk_index))
        merged, cur = [], None
        for c in selected_sorted:
            if (cur and c.document_id == cur["document_id"]
                    and 0 < c.chunk_index - cur["last_index"] <= 1
                    and c.chunk_type == "text"):
                cur["content"] += "\n" + (c.content or "")
                cur["last_index"] = c.chunk_index
                cur["chunk_ids"].append(c.chunk_id)
                cur["score"] = max(cur["score"], c.score)
                cur["methods"] |= set(c.methods or {c.method})
            else:
                if cur:
                    merged.append(cur)
                cur = {
                    "document_id": c.document_id, "page": c.page,
                    "chunk_ids": [c.chunk_id], "last_index": c.chunk_index,
                    "content": c.content or "", "score": c.score,
                    "methods": set(c.methods or {c.method}),
                    "chunk_type": c.chunk_type, "image_path": c.image_path,
                    "parent_index": c.parent_index,
                }
        if cur:
            merged.append(cur)
        # restore rank order (highest score first)
        merged.sort(key=lambda m: m["score"], reverse=True)
        items = merged
    else:
        items = [{
            "document_id": c.document_id, "page": c.page, "chunk_ids": [c.chunk_id],
            "content": c.content or "", "score": c.score,
            "methods": set(c.methods or {c.method}),
            "chunk_type": c.chunk_type, "image_path": c.image_path,
            "parent_index": c.parent_index, "last_index": c.chunk_index,
        } for c in selected]

    # 4) parent attach (hierarchical chunking) — budget permitting
    if cfg.attach_parents:
        wanted = {(m["document_id"], m["parent_index"])
                  for m in items if m.get("parent_index") is not None}
        parents = _parents(session_factory, space.id, wanted)
        for m in items:
            key = (m["document_id"], m.get("parent_index"))
            p = parents.get(key)
            if p and used + len(p) < budget and p[:120] not in m["content"]:
                m["content"] = p + "\n" + m["content"]
                used += len(p)

    # 4b) optional context compression (light built-in, or LLMLingua)
    if getattr(cfg, "compress_context", False):
        target = int(cfg.context_token_budget)
        for m in items:
            if getattr(cfg, "compressor", "light") == "llmlingua" and len(m["content"]) > 1500:
                m["content"] = _compress_llmlingua(m["content"], max(200, target // max(len(items), 1)))
            else:
                m["content"] = _compress_light(m["content"])

    # 5) resolve document names + final shape
    names = _doc_names(session_factory, {m["document_id"] for m in items})
    out = []
    for m in items:
        out.append({
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
        })
    return {"items": out, "chars": used}
