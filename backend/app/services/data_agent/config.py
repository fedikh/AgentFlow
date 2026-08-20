"""
Data Agent — configuration (Pydantic).

Three independent configs, each persisted on the data_sources row and each
loadable in isolation:

    GenerationConfig   how the LLM writes SQL (temperature, max tokens,
                       default vs custom system prompt)
    RetrievalConfig    how the three knowledge indexes are searched
                       (hybrid vector+keyword, RRF, per-index top-k, rerank)
    ChunkingConfig     per-format chunking of uploaded documents — the same
                       strategy catalog as the RAG spaces

Precedence, like services/retrieval/config.py: dataclass defaults →
per-source JSON overrides. Unknown keys are ignored so an older row never
breaks a newer schema.
"""
from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# The three knowledge indexes of the Data Agent (the RAG Index of the
# architecture diagram). Each is searched separately so one kind can never
# crowd the others out of the prompt.
KIND_DDL = "ddl"            # CREATE TABLE definitions + relationships
KIND_SQL = "sql"            # verified question → SQL pairs (few-shot)
KIND_BUSINESS = "business"  # descriptions, sample values, glossary, documents
KINDS = (KIND_DDL, KIND_SQL, KIND_BUSINESS)


class GenerationConfig(BaseModel):
    """LLM behaviour for SQL generation."""
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    max_tokens: int = Field(default=2000, ge=256, le=8000)
    prompt_mode: Literal["default", "custom"] = "default"
    system_prompt: str = ""          # only used when prompt_mode == "custom"
    max_retries: int = Field(default=3, ge=1, le=5)   # SQL correction loop cap
    send_results_to_llm: bool = False  # rows leaving the DB is opt-in


class RetrievalConfig(BaseModel):
    """How the three indexes are searched before generation.

    Same engine and same knobs as the RAG-space Retrieval panel — query
    enhancement, cross-encoder re-ranker (BGE local / Voyage), RRF and the
    candidate funnel — with ONE difference: search is ALWAYS hybrid here.

    That is not a toggle: schema knowledge is made of rare literal tokens
    (table and column names, KPI codes) that embeddings match poorly, and of
    business phrasing that keyword search misses entirely. Each branch covers
    the other's blind spot, so disabling either one only ever loses recall —
    which is why there is no `search_mode` field.
    """
    # ── query enhancement (RAG: transform_enabled) ──
    # One LLM call per question, computed once and shared by the three
    # indexes. Off by default here: this path is latency-sensitive and most
    # of what it searches is literal schema text.
    transform_enabled: bool = False

    # ── fusion ──
    rrf_k: int = Field(default=60, ge=1, le=200)
    # candidates pulled per branch BEFORE fusion
    fetch_k: int = Field(default=20, ge=1, le=100)
    keyword_k: int = Field(default=20, ge=1, le=100)

    # ── cross-encoder re-ranking (same models/keys as a RAG space) ──
    rerank: bool = False              # RAG has it always on; here it costs one
                                      # pass per index, so it stays a choice
    reranker_provider: Literal["bge", "voyage"] = "bge"
    reranker_model: str = ""          # "" = provider default
    reranker_key_source: Literal["company", "own"] = "company"
    # Voyage own key — Fernet-encrypted INSIDE retrieval_params, so no column
    # is added to data_sources. Never returned to the client in clear.
    reranker_api_key_enc: str = ""
    rerank_top_n: int = Field(default=10, ge=1, le=50)
    rerank_char_cap: int = Field(default=600, ge=100, le=4000)

    # ── final count kept per index (the "RAG Index" fan-out of the diagram) ──
    n_ddl: int = Field(default=10, ge=1, le=100)
    n_sql: int = Field(default=5, ge=0, le=50)
    n_business: int = Field(default=8, ge=0, le=50)

    def top_n(self, kind: str) -> int:
        return {KIND_DDL: self.n_ddl, KIND_SQL: self.n_sql,
                KIND_BUSINESS: self.n_business}.get(kind, 10)

    def public(self) -> dict:
        """What the UI may see — the encrypted key never leaves the backend."""
        d = self.model_dump(exclude={"reranker_api_key_enc"})
        d["reranker_has_own_key"] = bool(self.reranker_api_key_enc)
        return d


class ChunkingConfig(BaseModel):
    """Per-format chunking of knowledge documents — same catalog as RAG.
    format_map: {"pdf": {"strategy": "heading", "params": {...}}, …}
    An unlisted format falls back to the catalog's recommended strategy."""
    format_map: dict = Field(default_factory=dict)

    def for_format(self, file_type: str) -> tuple[str, dict]:
        entry = (self.format_map or {}).get((file_type or "").lower()) or {}
        return entry.get("strategy") or "", entry.get("params") or {}


def _load_json(raw) -> dict:
    if not raw:
        return {}
    try:
        v = json.loads(raw) if isinstance(raw, str) else raw
        return v if isinstance(v, dict) else {}
    except Exception as e:
        logger.warning(f"[DATA-AGENT] bad JSON config ignored: {e}")
        return {}


def generation_config(source) -> GenerationConfig:
    return GenerationConfig(
        temperature=float(getattr(source, "llm_temperature", 0.0) or 0.0),
        max_tokens=int(getattr(source, "llm_max_tokens", 2000) or 2000),
        prompt_mode=(getattr(source, "prompt_mode", "default") or "default"),
        system_prompt=getattr(source, "system_prompt", "") or "",
        send_results_to_llm=bool(getattr(source, "send_results_to_llm", False)),
    )


def retrieval_config(source) -> RetrievalConfig:
    data = _load_json(getattr(source, "retrieval_params", None))
    try:
        return RetrievalConfig(**{k: v for k, v in data.items()
                                  if k in RetrievalConfig.model_fields})
    except Exception as e:
        logger.warning(f"[DATA-AGENT] invalid retrieval config ({e}) — defaults")
        return RetrievalConfig()


def chunking_config(source) -> ChunkingConfig:
    return ChunkingConfig(format_map=_load_json(getattr(source, "chunk_params", None)))


def effective_mode(source) -> str:
    """'base' (whole schema in the prompt) or 'rag' (retrieve a subset)."""
    return getattr(source, "mode_override", None) or getattr(source, "mode_auto", "base") or "base"
