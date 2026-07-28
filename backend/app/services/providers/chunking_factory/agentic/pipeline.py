"""
Agentic chunking pipeline (OpenAI) — enterprise edition.

A document flows through seven cooperating agents:

    Document Intelligence  → rich profile: type, language, paragraph/table/
                             code density, heading quality, complexity,
                             BEST STRATEGY + confidence
    Strategy Agent         → picks the chunking STRATEGY (heading / element /
                             semantic / llm-boundary / recursive), not just a size
    Boundary Agent         → LLM predicts paragraph groupings only — the engine
                             rebuilds text verbatim (see llm_client)
    Chunk Builder          → structure-preserving assembly per chosen strategy
    Chunk Reviewer         → merges tiny chunks, splits oversized, mends
                             mid-sentence cuts
    Metadata Agent         → STRUCTURED metadata per chunk (title, summary,
                             keywords, entities) stored in chunk["meta"] —
                             never mixed into the text
    Chunk Evaluator        → scores every chunk 0-100 (size fit, boundary
                             cleanliness, topic unity proxy, metadata); low
                             scores are sent back through the Reviewer once
                             (feedback loop)

Design guarantees:
  * Bounded cost — intelligence: 1 call; boundaries: only sections >1000 chars;
    metadata: batched + capped. Small/easy documents may cost ZERO extra calls.
  * Never breaks indexing — every stage has a non-LLM fallback; the whole
    pipeline degrades to structural chunking if OpenAI is unavailable.
  * Content-safe — the Boundary Agent only returns paragraph ids; text is
    rebuilt from the original, so the model cannot rewrite a single word.

The strategy tag on every chunk is "agentic". If the AI could not run, chunks
are tagged "agentic_fallback" so the UI stays truthful.
"""
import logging
import re as _re

from ..base import (
    elements_of, ordered, text_of, is_table,
    flatten_split, element_chunks, structure_chunks, group_by_heading,
    split_recursive, make_semantic_split,
)
from ..llm_client import make_llm_split, llm_json

logger = logging.getLogger(__name__)

STRATEGY = "agentic"
FALLBACK_STRATEGY = "agentic_fallback"

# Cost guards
_ANALYZE_SAMPLE = 6000       # chars of the document sent to Document Intelligence
_META_MAX_CHUNKS = 60        # cap chunks that get LLM metadata
_META_BATCH = 8              # chunks per metadata call
_META_SNIPPET = 480          # chars per chunk shown to the metadata agent
_EVAL_THRESHOLD = 70         # evaluator score under this → back to the Reviewer

_STRATEGIES = {"heading", "element", "semantic", "llm", "recursive"}


# ══════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════

def chunk(parsed, cfg):
    access = cfg.p("_llm") or None
    elements = elements_of(parsed)
    if not elements:
        return []

    # ── Tree documents (JSON/XML): the OPTIMAL chunking is deterministic —
    # one chunk per detected business record (record strategy, node fallback).
    # An LLM adds nothing here, so the agentic mode costs ZERO API calls and
    # tags the chunks with the strategy that actually produced them.
    if (cfg.file_type or "").lower() in ("json", "xml"):
        from ..semi_structured.record import chunk as record_chunk
        chunks = record_chunk(parsed, cfg)
        logger.info("[AGENTIC] tree document → %s chunking (deterministic, no LLM cost): %d chunks",
                    chunks[0].get("strategy") if chunks else "record", len(chunks))
        return chunks

    # ── Tabular documents (CSV/XLSX): same logic — one row = one chunk is
    # already the optimal deterministic answer; an LLM adds only cost.
    if (cfg.file_type or "").lower() in ("csv", "xlsx", "xls", "excel"):
        from ..tabular.row import chunk as row_chunk
        chunks = row_chunk(parsed, cfg)
        logger.info("[AGENTIC] tabular document → row chunking (deterministic, no LLM cost): %d chunks",
                    len(chunks))
        return chunks

    try:
        intel = _document_intelligence(access, elements, cfg)       # 1
        plan = _strategy_agent(intel, cfg, access)                  # 2
        chunks = _build(elements, plan, access)                     # 3+4
        chunks = _review(chunks, plan)                              # 5
        chunks = _metadata(access, chunks, plan)                    # 6
        chunks = _evaluate(chunks, plan)                            # 7 (+loop)
        chunks = _finalize(chunks)
        if chunks:
            if not access:
                logger.warning("[AGENTIC] no LLM access — chunks are structural (fallback tag)")
                for c in chunks:
                    c["strategy"] = FALLBACK_STRATEGY
            logger.info("[AGENTIC] %d chunks · strategy=%s · plan=%s",
                        len(chunks), plan.get("strategy"), plan)
            return chunks
    except Exception as e:
        logger.warning("[AGENTIC] pipeline failed (%s) → structural fallback", e)

    chunks = _fallback(elements)
    for c in chunks:
        c["strategy"] = FALLBACK_STRATEGY
    return chunks


# ══════════════════════════════════════════════════════════════
#  1. Document Intelligence Agent — rich profile, not just a size
# ══════════════════════════════════════════════════════════════

def _document_intelligence(access, elements, cfg) -> dict:
    # ── heuristic profile computed in code (free, always available) ──
    els = ordered(elements)
    n = len(els) or 1
    headings = [e for e in els if e.get("type") == "heading"]
    tables = [e for e in els if is_table(e)]
    code = [e for e in els if e.get("type") == "code"]
    paras = [text_of(e) for e in els
             if e.get("type") not in ("heading", "table", "image") and text_of(e)]
    avg_para = int(sum(len(p) for p in paras) / len(paras)) if paras else 0
    # heading quality: share of headings that look intentional (numbered/short)
    good_heads = [h for h in headings
                  if _re.match(r"^\s*\d+[\.\)]", text_of(h)) or len(text_of(h)) < 60]
    heading_quality = round(len(good_heads) / len(headings), 2) if headings else 0.0

    profile = {
        "doc_type": (cfg.file_type or "document"),
        "language": "unknown",
        "topics": [],
        "n_elements": n,
        "n_headings": len(headings),
        "heading_quality": heading_quality,
        "avg_paragraph_chars": avg_para,
        "table_density": round(len(tables) / n, 2),
        "code_density": round(len(code) / n, 2),
        "narrative_density": round(len(paras) / n, 2),
        "complexity": "medium",
        "best_strategy": "",
        "confidence": 0.0,
        "recommended_chunk_chars": 1200 if headings else 900,
    }
    if not access:
        return profile

    sample = _sample_text(elements, _ANALYZE_SAMPLE)
    if not sample:
        return profile

    sys = (
        "You are the Document Intelligence Agent in an agentic chunking "
        "pipeline. Analyze the sample and return JSON: "
        '{"doc_type": str, "language": str, "topics": [str], '
        '"complexity": "low"|"medium"|"high", '
        '"best_strategy": "heading"|"element"|"semantic"|"llm"|"recursive", '
        '"confidence": 0.0-1.0, "recommended_chunk_chars": int (400-2500)}. '
        "Strategy guide: heading=clean outline; element=table/figure heavy; "
        "semantic=long prose without structure; llm=mixed/complex topics; "
        "recursive=plain uniform text."
    )
    data = llm_json(access, sys, sample)
    if isinstance(data, dict):
        for k in ("doc_type", "language", "complexity"):
            if data.get(k):
                profile[k] = data[k]
        if isinstance(data.get("topics"), list):
            profile["topics"] = [str(t) for t in data["topics"]][:8]
        bs = str(data.get("best_strategy") or "").lower()
        if bs in _STRATEGIES:
            profile["best_strategy"] = bs
        try:
            profile["confidence"] = max(0.0, min(1.0, float(data.get("confidence"))))
        except (TypeError, ValueError):
            pass
        try:
            rc = int(data.get("recommended_chunk_chars") or 0)
            if 300 <= rc <= 3000:
                profile["recommended_chunk_chars"] = rc
        except (TypeError, ValueError):
            pass
    return profile


# ══════════════════════════════════════════════════════════════
#  2. Strategy Agent — picks the STRATEGY, then the sizes
# ══════════════════════════════════════════════════════════════

def _strategy_agent(intel: dict, cfg, access) -> dict:
    # strategy: trust the Intelligence Agent when confident; else decide by rules
    strategy = intel.get("best_strategy") if intel.get("confidence", 0) >= 0.6 else ""
    if not strategy:
        if intel["n_headings"] >= 3 and intel["heading_quality"] >= 0.5:
            strategy = "heading"
        elif intel["table_density"] >= 0.25 or intel["code_density"] >= 0.2:
            strategy = "element"
        elif intel["n_headings"] == 0 and intel["narrative_density"] >= 0.6:
            strategy = "llm" if access else "semantic"
        else:
            strategy = "llm" if access else "recursive"
    if strategy == "llm" and not access:
        strategy = "recursive"

    # size: user pin (>0) beats the analyzer's recommendation
    target = int(cfg.p("target_chars", 0) or intel.get("recommended_chunk_chars", 1200))
    target = max(400, min(2500, target))
    gran = str(cfg.p("granularity", "balanced") or "balanced").lower()
    if gran == "fine":
        target = int(target * 0.7)
    elif gran == "coarse":
        target = int(target * 1.4)
    target = max(300, min(3000, target))

    return {
        "strategy": strategy,
        "target_chars": target,
        "min_chars": int(cfg.p("min_chars", 0) or max(120, target // 5)),
        "max_chars": int(target * 2),
        "overlap": int(cfg.p("chunk_overlap", 0) or max(40, target // 20)),
        "add_metadata": bool(cfg.p("generate_metadata", True)),
        "granularity": gran,
        "confidence": intel.get("confidence", 0),
    }


# ══════════════════════════════════════════════════════════════
#  3+4. Boundary Agent + Chunk Builder — build with the CHOSEN strategy
# ══════════════════════════════════════════════════════════════

def _build(elements, plan: dict, access):
    s, target = plan["strategy"], plan["target_chars"]
    if s == "heading":
        chunks = group_by_heading(elements, STRATEGY, plan["max_chars"])
    elif s == "element":
        chunks = structure_chunks(elements, STRATEGY, plan["max_chars"])
    elif s == "semantic":
        chunks = flatten_split(elements, make_semantic_split(target), STRATEGY)
    elif s == "llm":
        # Boundary Agent: id-validated paragraph grouping, verbatim rebuild,
        # engine-side overlap, GPT skipped for sections under 1000 chars.
        split_fn = make_llm_split(access, target, overlap=plan["overlap"])
        chunks = flatten_split(elements, split_fn, STRATEGY)
    else:   # recursive
        chunks = flatten_split(
            elements, lambda t: split_recursive(t, target, plan["overlap"]), STRATEGY)
    return chunks or _fallback(elements)


# ══════════════════════════════════════════════════════════════
#  5. Chunk Reviewer — size + boundary cleanup
# ══════════════════════════════════════════════════════════════

_SENT_END = (".", "!", "?", ":", "…", '"', "»", ")", "]", "|")


def _review(chunks: list, plan: dict) -> list:
    min_chars = plan["min_chars"]
    max_chars = plan["max_chars"]
    out = []
    for c in chunks:
        ctype = c.get("type", "text")
        content = (c.get("content") or "").strip()
        if not content:
            continue
        if ctype != "text":                      # tables/images: never re-cut
            out.append(c)
            continue
        # split oversized text chunks
        if len(content) > int(max_chars * 1.5):
            for piece in split_recursive(content, max_chars, max(48, max_chars // 10)):
                piece = piece.strip()
                if piece:
                    nc = dict(c)
                    nc["content"] = piece
                    out.append(nc)
            continue
        prev = out[-1] if out and out[-1].get("type", "text") == "text" else None
        same_page = prev is not None and prev.get("page") == c.get("page")
        fits = prev is not None and len(prev["content"]) + len(content) < int(max_chars * 1.3)
        # merge a tiny chunk into its same-page neighbour
        if len(content) < min_chars and same_page and fits:
            prev["content"] = prev["content"].rstrip() + "\n" + content
            continue
        # mend a mid-sentence cut: previous ends without punctuation AND this
        # one starts lowercase → they belong together
        if (same_page and fits and prev["content"].rstrip()
                and not prev["content"].rstrip().endswith(_SENT_END)
                and content[:1].islower()):
            prev["content"] = prev["content"].rstrip() + " " + content
            continue
        out.append(c)
    return out


# ══════════════════════════════════════════════════════════════
#  6. Metadata Agent — STRUCTURED metadata in chunk["meta"], never in the text
# ══════════════════════════════════════════════════════════════

def _metadata(access, chunks: list, plan: dict) -> list:
    if not access or not plan.get("add_metadata") or not chunks:
        return chunks

    targets = [i for i, c in enumerate(chunks)
               if c.get("type", "text") == "text"][:_META_MAX_CHUNKS]
    if not targets:
        return chunks

    sys = (
        "You are the Metadata Agent in a chunking pipeline. For each numbered "
        "text chunk return: a descriptive title (<=8 words), a one-sentence "
        "summary (<=25 words), 3-6 keywords, and up to 5 named entities "
        "(people, companies, codes) if present. Reply JSON: {\"items\": "
        "[{\"index\": int, \"title\": str, \"summary\": str, "
        "\"keywords\": [str], \"entities\": [str]}]}. Use the given indexes."
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
            meta = {
                "title": str(it.get("title") or "").strip()[:120],
                "summary": str(it.get("summary") or "").strip()[:300],
                "keywords": [str(k).strip() for k in (it.get("keywords") or [])
                             if str(k).strip()][:6],
                "entities": [str(e).strip() for e in (it.get("entities") or [])
                             if str(e).strip()][:5],
            }
            if meta["title"] or meta["keywords"]:
                chunks[i]["meta"] = {**(chunks[i].get("meta") or {}), **meta}
    return chunks


# ══════════════════════════════════════════════════════════════
#  7. Chunk Evaluator — scores 0-100; low scores loop back to the Reviewer
# ══════════════════════════════════════════════════════════════

def _score(c, plan) -> int:
    if c.get("type", "text") != "text":
        return 90                                    # tables/images: kept whole by design
    content = c.get("content") or ""
    target = plan["target_chars"]
    score = 100
    # size fitness
    if len(content) < plan["min_chars"]:
        score -= 30
    elif len(content) > plan["max_chars"] * 1.5:
        score -= 25
    elif not (target * 0.3 <= len(content) <= target * 1.8):
        score -= 10
    # boundary cleanliness
    if not content.rstrip().endswith(_SENT_END):
        score -= 15
    if content[:1].islower():
        score -= 10
    # topic-unity proxy: very many paragraphs in one chunk = probably mixed
    if content.count("\n\n") > 8:
        score -= 10
    # metadata quality (only when the Metadata Agent ran)
    if plan.get("add_metadata") and c.get("meta") is not None and not (c.get("meta") or {}).get("title"):
        score -= 10
    return max(0, score)


def _evaluate(chunks: list, plan: dict) -> list:
    scored = [(c, _score(c, plan)) for c in chunks]
    low = [c for c, s in scored if s < _EVAL_THRESHOLD]
    if low:
        # feedback loop: one more Reviewer pass over everything (merges the
        # fragments / splits the oversized that caused the low scores)
        logger.info("[AGENTIC] evaluator: %d/%d chunks under %d → reviewer loop",
                    len(low), len(chunks), _EVAL_THRESHOLD)
        chunks = _review(chunks, plan)
        scored = [(c, _score(c, plan)) for c in chunks]
    for c, s in scored:
        c["meta"] = {**(c.get("meta") or {}), "quality": s}
    avg = round(sum(s for _, s in scored) / len(scored)) if scored else 0
    logger.info("[AGENTIC] evaluator: avg quality %d/100", avg)
    return [c for c, _ in scored]


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
