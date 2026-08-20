"""
Vanna client — composition of the store (persistence + hybrid retrieval) and
the LLM binding, plus the two rules that keep it safe:

  1. `run_sql` is REPLACED the moment the instance is built, in this very
     function, with the validated executor. No code path — including any
     Vanna helper — can reach a database with unvalidated SQL.
  2. `vn.ask()` is never used: LangGraph orchestrates the same steps so we
     get timings, the bounded correction loop and a decision trace.

Instances are cached per (source, updated_at): the store opens DB sessions
and the LLM client keeps a connection pool, so building one per request
would be wasteful; a config change naturally evicts the stale instance.
"""
from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

_CACHE: dict = {}
_LOCK = threading.Lock()
_CACHE_MAX = 8


def _n_results_for(source, retrieval_cfg):
    """base mode retrieves EVERYTHING trained (deterministic, no retrieval
    variance); rag mode uses the configured per-index top-k."""
    from app.services.data_agent.config import effective_mode
    if effective_mode(source) == "base":
        wide = max(int(source.table_count or 0) + 20, 30)
        return retrieval_cfg.model_copy(update={
            "n_ddl": wide, "n_business": max(retrieval_cfg.n_business, 20),
            "n_sql": max(retrieval_cfg.n_sql, 10),
            "fetch_k": max(retrieval_cfg.fetch_k, wide),
            "keyword_k": max(retrieval_cfg.keyword_k, wide)})
    return retrieval_cfg


def build(db, source):
    """Compose store + LLM for THIS source (Vanna's intended pattern)."""
    from app.services.data_agent.config import (generation_config,
                                                retrieval_config)
    from app.services.data_agent.database import adapter_for
    from app.services.data_agent.vanna.prompts import build_system_rules
    from app.services.data_agent.vanna.store import build_store_class
    from app.services.llm_factory.resolver import resolve_llm_config

    gen = generation_config(source)
    retrieval = _n_results_for(source, retrieval_config(source))
    llm_cfg = resolve_llm_config(db, source)
    family = str(llm_cfg.get("family") or "").upper()
    Store = build_store_class()

    config = {
        "model": llm_cfg["model"],
        "temperature": gen.temperature,
        "max_tokens": gen.max_tokens,
        "retrieval_config": retrieval,
        "initial_prompt": None,
    }

    if family == "OLLAMA":
        from vanna.ollama import Ollama

        class _V(Store, Ollama):
            def __init__(self, source_id, config=None):
                Store.__init__(self, source_id=source_id, config=config)
                Ollama.__init__(self, config=config)

        config["ollama_host"] = llm_cfg.get("base_url") or "http://localhost:11434"
        vn = _V(source_id=source.id, config=config)
    else:
        from openai import OpenAI
        from vanna.openai import OpenAI_Chat

        class _V(Store, OpenAI_Chat):
            def __init__(self, source_id, client=None, config=None):
                Store.__init__(self, source_id=source_id, config=config)
                OpenAI_Chat.__init__(self, client=client, config=config)

        kwargs = {"api_key": llm_cfg.get("api_key") or "missing"}
        if family == "GROQ":
            kwargs["base_url"] = "https://api.groq.com/openai/v1"
        elif llm_cfg.get("base_url"):
            kwargs["base_url"] = llm_cfg["base_url"]
        vn = _V(source_id=source.id, client=OpenAI(**kwargs), config=config)

    adapter = adapter_for(source.dialect)
    vn.dialect = source.dialect
    # Vanna appends static_documentation to every prompt — this is where the
    # agent's rules (default or the IT's custom prompt + safety) live.
    vn.static_documentation = build_system_rules(
        source.dialect, gen.prompt_mode, gen.system_prompt or "")
    _attach_safe_run_sql(vn, source.id)
    vn._adapter = adapter
    return vn


def _attach_safe_run_sql(vn, source_id: str):
    """The single most important line in the module: Vanna's executor is
    replaced by the validated one, in the same function that builds it."""
    def safe_run_sql(sql: str):
        import pandas as pd

        from app.services.data_agent.nodes.execute_sql import run_validated
        result = run_validated(source_id, sql)
        return pd.DataFrame(result["rows"], columns=result["columns"])

    vn.run_sql = safe_run_sql
    vn.run_sql_is_set = True
    return vn


def get_client(db, source):
    """Cached, config-fresh Vanna instance."""
    key = (source.id, str(source.updated_at))
    with _LOCK:
        hit = _CACHE.get(key)
    if hit is not None:
        return hit
    vn = build(db, source)
    with _LOCK:
        for k in [k for k in _CACHE if k[0] == source.id]:
            _CACHE.pop(k, None)
        while len(_CACHE) >= _CACHE_MAX:
            _CACHE.pop(next(iter(_CACHE)), None)
        _CACHE[key] = vn
    return vn


def evict(source_id: str) -> None:
    with _LOCK:
        for k in [k for k in _CACHE if k[0] == source_id]:
            _CACHE.pop(k, None)
