"""
Chunking Factory — per-format, parameter-driven manual chunking.

Organised by parser category (documents / semi_structured / tabular / web). Each
category exposes only the strategies that fit it; the user picks a strategy and
tunes its parameters, applied globally (SINGLE) or per-document (PER_DOCUMENT).
Chunking consumes the rich `elements[]` schema, not the flattened blocks.

Public API:
    chunk_document(parsed_doc, cfg)      → list[chunk dict]
    catalog_for(file_type)               → {category, strategies:[…]} for the UI
    resolve_config(space, doc)           → ChunkConfig (mode-aware, validated)

Agentic / auto-selection is a separate, later phase (not here).
"""
import json
import importlib
import logging

from .base import ChunkConfig
from .registry import (
    STRATEGY_CATALOG, FILE_CATEGORY, category_for,
    strategies_for, default_strategy, strategy_def, default_params,
    ALLOWED_STRATEGIES, RECOMMENDED_BY_TYPE, AGENTIC_PARAMS, AGENTIC_STAGES,
)

logger = logging.getLogger(__name__)

_PKG = "app.services.providers.chunking_factory"


# ══════════════════════════════════════════════════════════════
#  Dispatch
# ══════════════════════════════════════════════════════════════

def chunk_document(parsed_doc, cfg: ChunkConfig) -> list:
    """Run one strategy over a ParsedDocument and return chunk dicts.

    Picks the category from cfg.file_type (falls back to the parsed document's
    file_type/category), resolves the strategy module, and validates against the
    catalog — falling back to the category's recommended default if the requested
    strategy isn't valid for this format.

    The "agentic" strategy is a special, format-agnostic pipeline (Agentic mode)
    and bypasses the per-format catalog.
    """
    file_type = cfg.file_type or getattr(parsed_doc, "file_type", "") or getattr(parsed_doc, "category", "")

    # ── Agentic mode: format-agnostic multi-agent pipeline ──
    if (cfg.strategy or "").lower() == "agentic":
        from .agentic import chunk as agentic_chunk
        logger.info(f"[CHUNK] {file_type} · strategy=agentic · params={cfg.params}")
        chunks = agentic_chunk(parsed_doc, cfg) or []
        for i, c in enumerate(chunks):
            c["chunk_index"] = i
            c.setdefault("strategy", "agentic")
            c.setdefault("type", "text")
        return chunks

    category = category_for(file_type)

    name = (cfg.strategy or "").lower()
    sdef = strategy_def(file_type, name)
    if not sdef:
        name = default_strategy(file_type)
        sdef = strategy_def(file_type, name)
        logger.warning(f"[CHUNK] strategy '{cfg.strategy}' invalid for {file_type} "
                       f"({category}); using default '{name}'")

    # merge provided params over the strategy defaults
    params = {**default_params(file_type, name), **(cfg.params or {})}
    run_cfg = ChunkConfig(strategy=name, params=params, file_type=file_type)

    module = importlib.import_module(f"{_PKG}.{category}.{sdef['module']}")
    logger.info(f"[CHUNK] {file_type}/{category} · strategy={name} · params={params}")
    chunks = module.chunk(parsed_doc, run_cfg) or []

    # normalize: guarantee sequential chunk_index + the strategy tag
    for i, c in enumerate(chunks):
        c["chunk_index"] = i
        c.setdefault("strategy", name)
        c.setdefault("type", "text")
    return chunks


# ══════════════════════════════════════════════════════════════
#  Catalog (for the frontend)
# ══════════════════════════════════════════════════════════════

def catalog_for(file_type: str = None) -> dict:
    """Strategy catalog for one file type (only its valid strategies, with the
    per-type recommended marked), or the whole catalog + allow-lists when
    file_type is falsy. Shaped for the chunking config UI."""
    if file_type:
        ft = file_type.lower()
        rec = default_strategy(ft)
        strategies = [
            {**{k: v for k, v in d.items() if k != "module"},
             "recommended": d["name"] == rec}
            for d in strategies_for(ft)
        ]
        return {"file_type": ft, "category": category_for(ft),
                "default": rec, "strategies": strategies}
    return {
        "categories": {
            cat: {"default": _default_of(cat), "strategies": _public(defs)}
            for cat, defs in STRATEGY_CATALOG.items()
        },
        "file_category": FILE_CATEGORY,
        "allowed": ALLOWED_STRATEGIES,          # file_type → [strategy names]
        "recommended": RECOMMENDED_BY_TYPE,     # file_type → recommended name
        # Agentic mode (not per-format): its pipeline stages + tunable params.
        "agentic": {"params": AGENTIC_PARAMS, "stages": AGENTIC_STAGES},
    }


def _default_of(category):
    for s in STRATEGY_CATALOG.get(category, []):
        if s.get("recommended"):
            return s["name"]
    defs = STRATEGY_CATALOG.get(category, [])
    return defs[0]["name"] if defs else None


def _public(defs):
    """Strip the internal `module` key; keep everything the UI renders."""
    return [{k: v for k, v in d.items() if k != "module"} for d in defs]


# ══════════════════════════════════════════════════════════════
#  Config resolution (SINGLE vs PER_DOCUMENT)
# ══════════════════════════════════════════════════════════════

def _load_params(raw) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def resolve_config(space, doc) -> ChunkConfig:
    """Build the ChunkConfig for a document from the space/document settings.

    PER_DOCUMENT: use the document's own strategy+params (falling back to the
    space's, then the category default). SINGLE (default): use the space's.
    The strategy is validated against the document's format; params merge over
    the strategy's declared defaults.
    """
    file_type = (getattr(doc, "file_type", "") or "").lower()
    mode = _norm_mode(getattr(space, "chunk_mode", None))

    # AGENTIC: one multi-agent pipeline for every document, tuned by the space's
    # chunk_params (granularity / target_chars / generate_metadata).
    if mode == "AGENTIC":
        params = _load_params(getattr(space, "chunk_params", None))
        return ChunkConfig(strategy="agentic", params=params, file_type=file_type)

    if mode == "PER_DOCUMENT":
        strategy = (getattr(doc, "chunk_strategy", None)
                    or getattr(space, "chunk_strategy", None))
        params = _load_params(getattr(doc, "chunk_params", None)
                              or getattr(space, "chunk_params", None))
    else:  # SINGLE — one strategy PER FORMAT
        fmt_map = _load_params(getattr(space, "chunk_format_map", None))
        entry = fmt_map.get(file_type) or {}
        strategy = entry.get("strategy") or getattr(space, "chunk_strategy", None)
        params = entry.get("params") or {}

    strategy = (str(strategy).lower() if strategy else default_strategy(file_type))
    if not strategy_def(file_type, strategy):
        strategy = default_strategy(file_type)

    # legacy space size/overlap as a fallback for size-based strategies
    if "chunk_size" not in params and getattr(space, "chunk_size", None):
        params.setdefault("chunk_size", space.chunk_size)
    if "chunk_overlap" not in params and getattr(space, "chunk_overlap", None) is not None:
        params.setdefault("chunk_overlap", space.chunk_overlap)

    return ChunkConfig(strategy=strategy, params=params, file_type=file_type)


def _norm_mode(mode) -> str:
    m = (str(mode.value) if hasattr(mode, "value") else str(mode or "")).upper()
    if m == "AGENTIC":
        return "AGENTIC"
    if m in ("PER_DOCUMENT", "PER_DOC"):
        return "PER_DOCUMENT"
    return "SINGLE"          # SINGLE, legacy FIXED_ALL, legacy ADAPTIVE → SINGLE


# ══════════════════════════════════════════════════════════════
#  LLM access injection (for the "llm" strategy and Agentic mode)
# ══════════════════════════════════════════════════════════════

def needs_llm(cfg: ChunkConfig) -> bool:
    """True when the resolved config uses an OpenAI-backed strategy."""
    return (cfg.strategy or "").lower() in ("llm", "agentic")


def inject_llm_access(db, space, cfg: ChunkConfig) -> None:
    """Resolve an OpenAI access config from the space/db and stash it under the
    private '_llm' param so the llm/agentic chunk modules can use it. No-op (and
    never raises) when no key is available — those strategies then fall back to
    structural chunking."""
    try:
        from .llm_client import resolve_openai
        access = resolve_openai(db, space)
    except Exception as e:
        logger.warning(f"[CHUNK] LLM access resolve failed: {e}")
        access = None
    cfg.params = dict(cfg.params or {})
    cfg.params["_llm"] = access


__all__ = [
    "chunk_document", "catalog_for", "resolve_config",
    "needs_llm", "inject_llm_access",
    "ChunkConfig", "STRATEGY_CATALOG", "category_for",
    "strategies_for", "default_strategy",
]
