"""
Chunking Factory — modular, registry-based (mirrors the loaders/parsers layout).

Each strategy lives in `strategies/<name>.py` and exposes `chunk(blocks, opts)`.
The registry below maps a canonical strategy name → its module + UI metadata.
`chunk_document()` is the single entry point used by rag_service and keeps the
3 modes (FIXED_ALL / PER_DOCUMENT / ADAPTIVE) from before.

    from app.services.providers.chunking import chunk_document
    chunks = chunk_document(content_blocks, space, document=doc)
"""
import importlib
import logging

from .base import ChunkOptions

logger = logging.getLogger(__name__)

_PKG = "app.services.providers.chunking.strategies"

# ── Strategy registry ──────────────────────────────────────────────
# name → {module, label, stars, best_for, pros, cons}
# Legacy DB values FIXED / SEMANTIC / HIERARCHICAL are kept as-is.
STRATEGIES = {
    "FIXED":          {"module": "fixed",          "label": "Fixed-size (overlap)", "stars": 5, "best_for": ["txt", "simple text"], "pros": "Fast, simple, solid RAG baseline", "cons": "Can split sentences"},
    "RECURSIVE":      {"module": "recursive",      "label": "Recursive",            "stars": 5, "best_for": ["pdf", "docx"], "pros": "Preserves structure (para→line→word)", "cons": "Slightly slower"},
    "CHARACTER":      {"module": "character",      "label": "Character-based",       "stars": 3, "best_for": ["simple text"], "pros": "Fully deterministic", "cons": "Can cut mid-word"},
    "TOKEN":          {"module": "token",          "label": "Token-based (LlamaIndex)", "stars": 5, "best_for": ["llm"], "pros": "Aligns to the LLM tokenizer", "cons": "Token-sized, not char"},
    "SENTENCE":       {"module": "sentence",       "label": "Sentence-based (LlamaIndex)", "stars": 4, "best_for": ["articles", "books", "docs"], "pros": "Never splits a sentence", "cons": "Uneven sizes"},
    "PARAGRAPH":      {"module": "paragraph",      "label": "Paragraph-based",       "stars": 4, "best_for": ["articles"], "pros": "Keeps paragraphs whole", "cons": "Uneven sizes"},
    "HEADER":         {"module": "header",         "label": "Section / header",      "stars": 5, "best_for": ["markdown", "docx", "manuals"], "pros": "Uses document structure", "cons": "Needs headings"},
    "PAGE":           {"module": "page",           "label": "Page-based",            "stars": 3, "best_for": ["scanned pdf"], "pros": "One page = one chunk", "cons": "Coarse"},
    "SLIDE":          {"module": "slide",          "label": "Slide-based",           "stars": 5, "best_for": ["pptx"], "pros": "One slide = one chunk", "cons": "PPTX only"},
    "SLIDING_WINDOW": {"module": "sliding_window", "label": "Sliding window",        "stars": 4, "best_for": ["dense text"], "pros": "Max context redundancy", "cons": "More chunks"},
    "SEMANTIC":       {"module": "semantic",       "label": "Semantic",              "stars": 5, "best_for": ["pdf", "mixed topics"], "pros": "Splits on topic change", "cons": "Needs embeddings, slower"},
    "HIERARCHICAL":   {"module": "hierarchical",   "label": "Hierarchical (parent-child)", "stars": 5, "best_for": ["advanced rag"], "pros": "Retrieve child, expand with parent", "cons": "More chunks stored"},
    "DOCUMENT_STRUCTURE": {"module": "document_structure", "label": "Document structure", "stars": 5, "best_for": ["docling", "json", "xml"], "pros": "Each element (title/table/figure) intact", "cons": "Depends on parser quality"},
    "ROW":            {"module": "row",            "label": "Row-based",             "stars": 5, "best_for": ["csv", "excel"], "pros": "Each row is a clean unit", "cons": "Tabular only"},
    # Aliases
    "FIXED_OVERLAP":  {"module": "fixed",          "label": "Fixed-size with overlap", "stars": 5, "best_for": ["txt"], "pros": "Overlap keeps context", "cons": "Can split sentences", "alias_of": "FIXED"},
    "TABLE_AWARE":    {"module": "fixed",          "label": "Table-aware",           "stars": 5, "best_for": ["financial"], "pros": "Tables kept intact (always, in every strategy)", "cons": "—", "alias_of": "FIXED"},
}

# File-type → high-level category (for grouping the Uploads/Chunking UI).
FILE_CATEGORY = {
    "pdf": "document", "docx": "document", "pptx": "document",
    "txt": "document", "md": "document", "markdown": "document",
    "csv": "structured", "xlsx": "structured", "xls": "structured",
    "json": "structured", "xml": "structured",
    "html": "web", "htm": "web", "url": "web",
}

# Which strategies actually make sense for each file type. A CSV can't be
# sentence-chunked; a slide split only applies to PPTX, etc. The UI filters to
# these, and the factory still falls back to FIXED for anything unexpected.
ALLOWED_STRATEGIES = {
    # ── documents ──
    "pdf":  ["RECURSIVE", "FIXED", "CHARACTER", "TOKEN", "SENTENCE", "PARAGRAPH", "HEADER", "PAGE", "SLIDING_WINDOW", "SEMANTIC", "HIERARCHICAL", "DOCUMENT_STRUCTURE"],
    "docx": ["HEADER", "RECURSIVE", "FIXED", "CHARACTER", "TOKEN", "SENTENCE", "PARAGRAPH", "SLIDING_WINDOW", "SEMANTIC", "HIERARCHICAL", "DOCUMENT_STRUCTURE"],
    "pptx": ["SLIDE", "FIXED", "RECURSIVE", "TOKEN", "SENTENCE", "PARAGRAPH", "SEMANTIC", "DOCUMENT_STRUCTURE"],
    "txt":  ["FIXED", "RECURSIVE", "CHARACTER", "TOKEN", "SENTENCE", "PARAGRAPH", "SLIDING_WINDOW", "SEMANTIC"],
    "md":   ["HEADER", "FIXED", "RECURSIVE", "PARAGRAPH", "SENTENCE", "TOKEN", "SEMANTIC", "DOCUMENT_STRUCTURE"],
    "markdown": ["HEADER", "FIXED", "RECURSIVE", "PARAGRAPH", "SENTENCE", "TOKEN", "SEMANTIC", "DOCUMENT_STRUCTURE"],
    # ── structured data ──
    "csv":  ["ROW", "DOCUMENT_STRUCTURE"],
    "xlsx": ["ROW", "DOCUMENT_STRUCTURE"],
    "xls":  ["ROW", "DOCUMENT_STRUCTURE"],
    "json": ["DOCUMENT_STRUCTURE", "RECURSIVE", "FIXED"],
    "xml":  ["DOCUMENT_STRUCTURE", "RECURSIVE", "FIXED"],
    # ── web ──
    "html": ["RECURSIVE", "FIXED", "HEADER", "PARAGRAPH", "SENTENCE", "TOKEN", "SEMANTIC", "DOCUMENT_STRUCTURE"],
    "htm":  ["RECURSIVE", "FIXED", "HEADER", "PARAGRAPH", "SENTENCE", "TOKEN", "SEMANTIC", "DOCUMENT_STRUCTURE"],
    "url":  ["RECURSIVE", "FIXED", "HEADER", "PARAGRAPH", "SENTENCE", "TOKEN", "SEMANTIC", "DOCUMENT_STRUCTURE"],
}


def allowed_for(file_type: str) -> list[str]:
    """Valid strategy names for a file type (all known if the type is unknown)."""
    ft = (file_type or "").lower()
    return ALLOWED_STRATEGIES.get(ft, [n for n, m in STRATEGIES.items() if "alias_of" not in m])


# Recommended strategies per uploaded file type (for the UI / Data Agent).
RECOMMENDED_BY_FILETYPE = {
    "pdf":  ["RECURSIVE", "SEMANTIC", "HIERARCHICAL"],
    "docx": ["HEADER", "RECURSIVE"],
    "pptx": ["SLIDE"],
    "txt":  ["FIXED"],
    "md":   ["HEADER"],
    "markdown": ["HEADER"],
    "csv":  ["ROW"],
    "xlsx": ["ROW"],
    "xls":  ["ROW"],
    "json": ["DOCUMENT_STRUCTURE"],
    "xml":  ["DOCUMENT_STRUCTURE"],
}

# Strategies ADAPTIVE tries then compares (kept small — expensive).
ADAPTIVE_CANDIDATES = ["FIXED", "HIERARCHICAL", "SEMANTIC"]


# UI grouping for the strategy catalog.
_GROUPS = {
    "FIXED": "Basic", "CHARACTER": "Basic", "TOKEN": "Basic", "SLIDING_WINDOW": "Basic",
    "RECURSIVE": "Structure-aware", "HEADER": "Structure-aware", "PARAGRAPH": "Structure-aware",
    "SENTENCE": "Structure-aware", "DOCUMENT_STRUCTURE": "Structure-aware",
    "PAGE": "Layout", "SLIDE": "Layout",
    "SEMANTIC": "Semantic", "HIERARCHICAL": "Advanced", "ROW": "Tabular",
}


def list_strategies() -> list[dict]:
    """Serializable strategy catalog (for the chunking config UI)."""
    return [
        {"name": name, "group": _GROUPS.get(name, "Other"),
         **{k: v for k, v in meta.items() if k != "module"}}
        for name, meta in STRATEGIES.items()
        if "alias_of" not in meta
    ]


def _resolve(strategy) -> str:
    name = strategy.value if hasattr(strategy, "value") else str(strategy or "FIXED")
    name = name.upper()
    return name if name in STRATEGIES else "FIXED"


def chunk_with_strategy(content_blocks, strategy, space, size=None, overlap=None) -> list[dict]:
    """Apply ONE strategy by name. `size`/`overlap` override the space defaults
    (used by PER_DOCUMENT mode for per-file sizing). Reusable by every mode."""
    name = _resolve(strategy)
    opts = ChunkOptions(
        chunk_size=size or space.chunk_size or 512,
        chunk_overlap=overlap if overlap is not None else (space.chunk_overlap or 50),
        strategy=name,
    )
    module = importlib.import_module(f"{_PKG}.{STRATEGIES[name]['module']}")
    logger.info(f"  strategy={name}, size={opts.chunk_size}, overlap={opts.chunk_overlap}")
    return module.chunk(content_blocks, opts)


def chunk_document(content_blocks: list[dict], space, document=None) -> list[dict]:
    """Entry point. Reads space.chunk_mode and routes to the right strategy."""
    mode = getattr(space, "chunk_mode", None) or "FIXED_ALL"
    logger.info(f"Chunking mode={mode}")

    if mode == "ADAPTIVE":
        return _adaptive_chunk(content_blocks, space, document)

    if mode == "PER_DOCUMENT":
        # Each document may override strategy, size AND overlap.
        strategy = (
            getattr(document, "chunk_strategy", None)
            or space.chunk_strategy
            or "FIXED"
        )
        d_size = getattr(document, "chunk_size", None)
        d_overlap = getattr(document, "chunk_overlap", None)
        return chunk_with_strategy(content_blocks, strategy, space, size=d_size, overlap=d_overlap)

    return chunk_with_strategy(content_blocks, space.chunk_strategy or "FIXED", space)


# ── ADAPTIVE: try candidates, keep the best (intrinsic size score) ──
def _adaptive_chunk(content_blocks, space, document=None) -> list[dict]:
    target = space.chunk_size or 512
    best_strategy, best_chunks, best_score = None, None, float("-inf")

    for strategy in ADAPTIVE_CANDIDATES:
        try:
            candidate = chunk_with_strategy(content_blocks, strategy, space)
            if not candidate:
                continue
            score = _size_score(candidate, target)
            logger.info(f"  [adaptive] {strategy}: {len(candidate)} chunks, score={score:.3f}")
            if score > best_score:
                best_strategy, best_chunks, best_score = strategy, candidate, score
        except Exception as e:
            logger.warning(f"  [adaptive] {strategy} failed: {e}")

    if best_chunks is None:
        best_strategy = "FIXED"
        best_chunks = chunk_with_strategy(content_blocks, "FIXED", space)

    logger.info(f"  [adaptive] WINNER = {best_strategy} (score={best_score:.3f})")
    if document is not None:
        try:
            document.chosen_strategy = best_strategy
        except Exception:
            pass
    for c in best_chunks:
        c["strategy"] = best_strategy
    return best_chunks


def _size_score(chunks: list[dict], target_size: int) -> float:
    """Fraction of chunks whose size is within 0.5×–1.5× the target."""
    if not chunks:
        return 0.0
    lo, hi = target_size * 0.5, target_size * 1.5
    return sum(1 for c in chunks if lo <= len(c["content"]) <= hi) / len(chunks)
