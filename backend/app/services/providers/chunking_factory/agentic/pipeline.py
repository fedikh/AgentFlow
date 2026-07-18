"""
Agentic chunking pipeline (OpenAI).

A document flows through six cooperating agents:

    Document Analyzer      → understands the document (type, topics, structure)
    Planning Agent         → turns that understanding into a concrete chunk plan
    Semantic Boundary Detector → finds coherent split points (LLM-backed)
    Chunk Builder          → assembles structure-preserving chunks
    Metadata Generator     → titles + keywords per chunk (embedded for retrieval)
    Quality Reviewer       → merges tiny chunks, splits oversized, cleans up

Design guarantees:
  * Bounded cost — LLM calls are capped (analysis: 1, boundaries: per-section via
    the shared splitter with structural fallback, metadata: batched + capped).
  * Never breaks indexing — every stage has a non-LLM fallback and the whole
    pipeline degrades to structural chunking if OpenAI is unavailable or errors.
  * Content-safe — the boundary detector validates length conservation, so text
    is only divided, never rewritten or dropped.

The strategy tag on every chunk is "agentic".
"""
import logging

from ..base import (
    elements_of, ordered, text_of, is_table,
    flatten_split, element_chunks, split_recursive,
)
from ..llm_client import make_llm_split, llm_json

logger = logging.getLogger(__name__)

STRATEGY = "agentic"

# Cost guards
_ANALYZE_SAMPLE = 6000       # chars of the document sent to the Analyzer
_META_MAX_CHUNKS = 60        # cap chunks that get LLM metadata
_META_BATCH = 8              # chunks per metadata call
_META_SNIPPET = 480          # chars per chunk shown to the metadata agent


# ══════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════

def chunk(parsed, cfg):
    access = cfg.p("_llm") or None
    elements = elements_of(parsed)
    if not elements:
        return []

    try:
        analysis = _analyze(access, elements, cfg)                 # 1
        plan = _plan(analysis, cfg)                                # 2
        split_fn = _boundary_detector(access, plan)                # 3
        chunks = _build(elements, split_fn)                        # 4
        chunks = _quality_review(chunks, plan)                     # 6 (pre-meta cleanup)
        chunks = _metadata(access, chunks, plan)                   # 5
        chunks = _finalize(chunks)
        if chunks:
            logger.info("[AGENTIC] %d chunks · plan=%s", len(chunks), plan)
            return chunks
    except Exception as e:
        logger.warning("[AGENTIC] pipeline failed (%s) → structural fallback", e)

    # Fallback: structure-preserving recursive chunking, tagged agentic.
    return _fallback(elements)


# ══════════════════════════════════════════════════════════════
#  1. Document Analyzer
# ══════════════════════════════════════════════════════════════

def _analyze(access, elements, cfg) -> dict:
    has_headings = any(el.get("type") == "heading" for el in elements)
    has_tables = any(is_table(el) for el in elements)
    file_type = (cfg.file_type or "").lower()

    heuristic = {
        "doc_type": file_type or "document",
        "language": "unknown",
        "topics": [],
        "has_clear_structure": has_headings,
        "density": "medium",
        "recommended_chunk_chars": 1200 if has_headings else 900,
    }
    if not access:
        return heuristic

    sample = _sample_text(elements, _ANALYZE_SAMPLE)
    if not sample:
        return heuristic

    sys = (
        "You are the Document Analyzer in an agentic chunking pipeline. Read the "
        "sample and describe the document so a planner can chunk it well. Return "
        'JSON: {"doc_type": str, "language": str, "topics": [str], '
        '"has_clear_structure": bool, "density": "low"|"medium"|"high", '
        '"recommended_chunk_chars": int}. recommended_chunk_chars in [400,2500].'
    )
    data = llm_json(access, sys, sample)
    if not isinstance(data, dict):
        return heuristic
    out = dict(heuristic)
    for k in ("doc_type", "language", "density"):
        if data.get(k):
            out[k] = data[k]
    if isinstance(data.get("topics"), list):
        out["topics"] = [str(t) for t in data["topics"]][:8]
    if isinstance(data.get("has_clear_structure"), bool):
        out["has_clear_structure"] = data["has_clear_structure"]
    try:
        rc = int(data.get("recommended_chunk_chars") or 0)
        if 300 <= rc <= 3000:
            out["recommended_chunk_chars"] = rc
    except (TypeError, ValueError):
        pass
    out["has_tables"] = has_tables
    return out


# ══════════════════════════════════════════════════════════════
#  2. Planning Agent  (deterministic — turns analysis + user knobs into a plan)
# ══════════════════════════════════════════════════════════════

def _plan(analysis: dict, cfg) -> dict:
    # User overrides from the space's agentic params, else analyzer's advice.
    target = int(cfg.p("target_chars", 0) or analysis.get("recommended_chunk_chars", 1200))
    target = max(400, min(2500, target))

    gran = str(cfg.p("granularity", "balanced") or "balanced").lower()
    if gran == "fine":
        target = int(target * 0.7)
    elif gran == "coarse":
        target = int(target * 1.4)
    target = max(300, min(3000, target))

    min_chars = int(cfg.p("min_chars", 0) or max(120, target // 5))
    add_metadata = bool(cfg.p("generate_metadata", True))

    return {
        "target_chars": target,
        "min_chars": min_chars,
        "max_chars": int(target * 2),
        "use_headings": bool(analysis.get("has_clear_structure", True)),
        "add_metadata": add_metadata,
        "granularity": gran,
    }


# ══════════════════════════════════════════════════════════════
#  3. Semantic Boundary Detector
# ══════════════════════════════════════════════════════════════

def _boundary_detector(access, plan):
    # The LLM splitter finds coherent boundaries; falls back to recursive.
    return make_llm_split(access, plan["target_chars"])


# ══════════════════════════════════════════════════════════════
#  4. Chunk Builder  (structure-preserving assembly)
# ══════════════════════════════════════════════════════════════

def _build(elements, split_fn):
    chunks = flatten_split(elements, split_fn, STRATEGY)
    return chunks or _fallback(elements)


# ══════════════════════════════════════════════════════════════
#  6. Quality Reviewer  (heuristic cleanup — runs before metadata)
# ══════════════════════════════════════════════════════════════

def _quality_review(chunks: list, plan: dict) -> list:
    min_chars = plan["min_chars"]
    max_chars = plan["max_chars"]
    out = []
    for c in chunks:
        ctype = c.get("type", "text")
        content = (c.get("content") or "").strip()
        if not content:
            continue
        if ctype != "text":
            out.append(c)
            continue
        # split oversized text chunks
        if len(content) > int(max_chars * 1.5):
            for piece in split_recursive(content, max_chars, max(48, max_chars // 10)):
                piece = piece.strip()
                if piece:
                    nc = dict(c); nc["content"] = piece
                    out.append(nc)
            continue
        # merge a tiny text chunk into the previous text chunk on the same page
        if (len(content) < min_chars and out
                and out[-1].get("type", "text") == "text"
                and out[-1].get("page") == c.get("page")
                and len(out[-1]["content"]) + len(content) < int(max_chars * 1.3)):
            out[-1]["content"] = out[-1]["content"].rstrip() + "\n" + content
            continue
        out.append(c)
    return out


# ══════════════════════════════════════════════════════════════
#  5. Metadata Generator  (titles + keywords, embedded into the chunk)
# ══════════════════════════════════════════════════════════════

def _metadata(access, chunks: list, plan: dict) -> list:
    if not access or not plan.get("add_metadata") or not chunks:
        return chunks

    targets = [i for i, c in enumerate(chunks)
               if c.get("type", "text") == "text"][:_META_MAX_CHUNKS]
    if not targets:
        return chunks

    sys = (
        "You are the Metadata Generator in a chunking pipeline. For each numbered "
        "text chunk, produce a short descriptive title (<=8 words) and 3-6 "
        "keywords. Return JSON: {\"items\": [{\"index\": int, \"title\": str, "
        "\"keywords\": [str]}]}. Use the same index numbers you are given."
    )

    for start in range(0, len(targets), _META_BATCH):
        batch = targets[start:start + _META_BATCH]
        payload = "\n\n".join(
            f"[{i}] {(chunks[i].get('content') or '')[:_META_SNIPPET]}" for i in batch
        )
        data = llm_json(access, sys, payload)
        items = (data or {}).get("items")
        if not isinstance(items, list):
            continue
        by_index = {}
        for it in items:
            try:
                by_index[int(it.get("index"))] = it
            except (TypeError, ValueError):
                continue
        for i in batch:
            it = by_index.get(i)
            if not it:
                continue
            title = str(it.get("title") or "").strip()
            kws = it.get("keywords") or []
            kws = [str(k).strip() for k in kws if str(k).strip()][:6] if isinstance(kws, list) else []
            header = _meta_header(title, kws)
            if header:
                chunks[i]["content"] = header + "\n" + chunks[i]["content"]
    return chunks


def _meta_header(title: str, keywords: list) -> str:
    parts = []
    if title:
        parts.append(f"[{title}]")
    if keywords:
        parts.append("Keywords: " + ", ".join(keywords))
    return " ".join(parts)


# ══════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════

def _finalize(chunks: list) -> list:
    out = []
    for c in chunks:
        if (c.get("content") or "").strip():
            c.setdefault("strategy", STRATEGY)
            c.setdefault("type", "text")
            out.append(c)
    for i, c in enumerate(out):
        c["chunk_index"] = i
    return out


def _fallback(elements) -> list:
    """Structure-preserving recursive chunking, tagged agentic."""
    try:
        chunks = flatten_split(
            elements,
            lambda t: split_recursive(t, 1000, 120),
            STRATEGY,
        )
        if chunks:
            return _finalize(chunks)
    except Exception:
        pass
    return _finalize(element_chunks(elements, STRATEGY, min_chars=120))


def _sample_text(elements, limit: int) -> str:
    buf, n = [], 0
    for el in ordered(elements):
        t = (text_of(el) or "").strip()
        if not t:
            continue
        buf.append(t)
        n += len(t)
        if n >= limit:
            break
    return "\n".join(buf)[:limit]
