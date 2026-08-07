"""
Retrieval Engine — configuration.

User-configurable (Retrieval panel):
    search_mode        "hybrid" | "vector" | "keyword"  — switchable any time
    transform_enabled  LLM query enhancement (rewrite / expansion / spell /
                       noise removal) — enabled by default
    reranker_provider  "bge" (BAAI/bge-reranker-v2-m3, local) |
                       "voyage" (rerank-2.5, own key encrypted per space)
    rrf_k              hybrid fusion constant
    top_k              final chunk count (classic panel field)

Everything else is a fixed production default. Precedence (later wins):
    defaults → retrieval.json (env RETRIEVAL_CONFIG_FILE) →
    per-space fields → space.retrieval_params.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, fields

logger = logging.getLogger(__name__)


@dataclass
class RetrievalConfig:
    # ── user-configurable ──
    search_mode: str = "hybrid"          # "hybrid" | "vector" | "keyword"
    transform_enabled: bool = True       # LLM query enhancement
    reranker_provider: str = "bge"       # "bge" | "voyage"
    reranker_model: str = ""             # "" = provider default
    reranker_key_source: str = "company" # voyage key: "company" (admin) | "own" (space)
    rrf_k: int = 60
    top_k: int = 5

    # ── fixed production defaults ──
    fetch_k: int = 30                    # vector candidates before fusion
    keyword_k: int = 30                  # keyword candidates before fusion
    rerank_top_n: int = 10               # candidates sent to the cross-encoder
    rerank_char_cap: int = 600           # chars of each chunk the reranker reads
                                         # (CPU time grows with length; relevance
                                         # signal is concentrated at the start)
    reranker_api_key: str = ""           # resolved at query time (space → provider → env)
    embed_cache_ttl: int = 3600          # query-embedding cache (0 = off)
    context_token_budget: int = 3000     # ≈ chars/4
    parallel: bool = True
    timeout_s: float = 8.0
    log_timings: bool = True


# Old key → current key ("" = dropped). Spaces saved by earlier UI versions
# keep loading without migration.
_LEGACY_KEYS = {
    "enhance": "transform_enabled",
    "rewrite_query": "transform_enabled",
    "enable_vector": "", "enable_keyword": "", "enable_dense": "",
    "enable_fts": "", "enable_bm25": "", "enable_exact": "",
    "enable_metadata_filters": "", "metadata_filters": "",
    "fts_k": "keyword_k", "semantic_weight": "", "dynamic_weights": "",
    "rerank": "", "merge_neighbors": "", "attach_parents": "",
    "fuzzy": "", "fuzzy_threshold": "", "iterative_scan": "",
    "hnsw_ef_search": "", "multi_query": "", "hyde": "",
}

_FILE_CACHE: dict = {"path": None, "mtime": None, "data": {}}


def _file_overrides() -> dict:
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
        _FILE_CACHE.update(path=path, mtime=mtime, data=data if isinstance(data, dict) else {})
        logger.info(f"[RETRIEVAL] config overrides from {path}: {list(_FILE_CACHE['data'])}")
    except Exception as e:
        logger.warning(f"[RETRIEVAL] bad config file {path}: {e}")
        return {}
    return _FILE_CACHE["data"]


def _apply(cfg: RetrievalConfig, overrides: dict, valid: set) -> None:
    for k, v in overrides.items():
        key = _LEGACY_KEYS.get(k, k)
        if key and key in valid and v is not None:
            setattr(cfg, key, v)


def load_config(space=None) -> RetrievalConfig:
    cfg = RetrievalConfig()
    valid = {f.name for f in fields(RetrievalConfig)}

    _apply(cfg, _file_overrides(), valid)

    if space is not None:
        cfg.top_k = int(getattr(space, "top_k", cfg.top_k) or cfg.top_k)
        raw = getattr(space, "retrieval_params", None)
        if raw:
            try:
                overrides = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(overrides, dict):
                    _apply(cfg, overrides, valid)
            except Exception as e:
                logger.warning(f"[RETRIEVAL] bad space.retrieval_params: {e}")

    if cfg.search_mode not in ("hybrid", "vector", "keyword"):
        cfg.search_mode = "hybrid"
    return cfg


def config_dict(cfg: RetrievalConfig) -> dict:
    return asdict(cfg)
