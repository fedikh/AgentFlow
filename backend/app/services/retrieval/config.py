"""
Retrieval Engine — single configuration point.

Precedence (later wins):
    1. Built-in defaults below
    2. Optional JSON file  (env RETRIEVAL_CONFIG_FILE, default backend/retrieval.json)
    3. Per-space settings  (top_k, semantic_weight, reranking_enabled, search_engine)

So an IT admin tunes the ENGINE once in retrieval.json, and each RAG space
keeps tuning its own top_k / weights / reranking from the existing Retrieval
panel — no new UI or migrations required.

Example retrieval.json:
{
  "enable_bm25": true,
  "enable_dense": true,
  "enable_metadata": true,
  "enable_exact": true,
  "fusion": "rrf",
  "rrf_k": 60,
  "mmr": false,
  "reranker_provider": "cross_encoder",
  "rerank_top_n": 25,
  "timeout_s": 8
}
"""
from __future__ import annotations

import json
import os
import logging
from dataclasses import dataclass, asdict, fields

logger = logging.getLogger(__name__)


@dataclass
class RetrievalConfig:
    # ── retriever toggles (each independently on/off) ──
    enable_dense: bool = True
    enable_bm25: bool = True
    enable_metadata: bool = True
    enable_exact: bool = True

    # ── dense retrieval ──
    top_k: int = 5
    fetch_k: int = 30                    # candidates pulled before MMR / fusion
    similarity_threshold: float = 0.0    # 0 = keep all
    mmr: bool = False                    # maximal marginal relevance diversification
    mmr_lambda: float = 0.6              # 1 = pure relevance, 0 = pure diversity

    # ── sparse (BM25 via bm25s) ──
    bm25_k: int = 30                     # candidates from BM25 before fusion
    bm25_cache_ttl_s: int = 300          # per-space corpus cache lifetime
    bm25_k1: float = 1.5                 # BM25 term-frequency saturation
    bm25_b: float = 0.75                 # BM25 length normalization

    # ── query transforms (LLM-based; use the space's LLM, degrade to no-op) ──
    rewrite_query: bool = False          # LLM rewrites vague queries
    hyde: bool = False                   # HyDE: embed a hypothetical answer
    multi_query: bool = False            # LLM generates query variants

    # ── fusion ──
    fusion: str = "rrf"                  # "rrf" | "weighted"
    rrf_k: int = 60
    semantic_weight: float = 0.7         # weighted fusion: dense weight (legacy knob)
    w_dense: float = 0.0                 # explicit per-retriever weights; 0 = derive
    w_bm25: float = 0.0                  #   from semantic_weight automatically
    w_metadata: float = 0.0

    # ── re-ranking (optional) ──
    rerank: bool = False
    # cross_encoder | bge | jina_local | flashrank | cohere | jina | voyage
    reranker_provider: str = "bge"
    reranker_model: str = ""             # "" = provider default
    rerank_top_n: int = 25               # how many fused candidates go to the reranker
    rerank_threshold: float = 0.0        # drop reranked results scoring below (0 = keep)

    # ── parent / hierarchical retrieval ──
    attach_parents: bool = True          # prepend the parent chunk (context)
    auto_merge_parents: bool = False     # AutoMerging: replace siblings by parent
    parent_merge_children: int = 2       # …when ≥ N children of one parent retrieved

    # ── context builder ──
    context_token_budget: int = 3000     # ≈ chars/4; final prompt context cap
    merge_neighbors: bool = True         # stitch adjacent chunks of the same doc
    compress_context: bool = False       # squeeze context before the LLM
    compressor: str = "light"            # "light" (built-in) | "llmlingua" (if installed)

    # ── execution ──
    parallel: bool = True
    timeout_s: float = 8.0               # per-retriever timeout
    log_timings: bool = True


_FILE_CACHE: dict = {"path": None, "mtime": None, "data": {}}


def _file_overrides() -> dict:
    """retrieval.json overrides, hot-reloaded on mtime change."""
    path = os.environ.get("RETRIEVAL_CONFIG_FILE", os.path.join(os.getcwd(), "retrieval.json"))
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {}
    if _FILE_CACHE["path"] == path and _FILE_CACHE["mtime"] == mtime:
        return _FILE_CACHE["data"]
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
        _FILE_CACHE.update(path=path, mtime=mtime, data=data)
        logger.info(f"[RETRIEVAL] loaded config overrides from {path}: {list(data)}")
        return data
    except Exception as e:
        logger.warning(f"[RETRIEVAL] bad config file {path}: {e}")
        return {}


def load_config(space=None) -> RetrievalConfig:
    cfg = RetrievalConfig()
    valid = {f.name for f in fields(RetrievalConfig)}

    # 2) file overrides
    for k, v in _file_overrides().items():
        if k in valid:
            setattr(cfg, k, v)

    # 3) per-space settings (the existing Retrieval panel keeps working)
    if space is not None:
        cfg.top_k = int(getattr(space, "top_k", cfg.top_k) or cfg.top_k)
        sw = getattr(space, "semantic_weight", None)
        if sw is not None:
            cfg.semantic_weight = float(sw)
        if getattr(space, "reranking_enabled", False):
            cfg.rerank = True
        engine = str(getattr(space, "search_engine", "") or "").upper()
        if engine and engine not in ("HYBRID", "ELASTICSEARCH"):
            # a non-hybrid engine means "dense only" was requested
            cfg.enable_bm25 = False

        # 4) per-space PIPELINE overrides (the visual Retrieval Pipeline UI):
        #    space.retrieval_params is a JSON blob of RetrievalConfig fields —
        #    the most specific layer, wins over everything.
        raw = getattr(space, "retrieval_params", None)
        if raw:
            try:
                overrides = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(overrides, dict):
                    for k, v in overrides.items():
                        if k in valid and v is not None:
                            setattr(cfg, k, v)
            except Exception as e:
                logger.warning(f"[RETRIEVAL] bad space.retrieval_params: {e}")
    return cfg


def config_dict(cfg: RetrievalConfig) -> dict:
    return asdict(cfg)
