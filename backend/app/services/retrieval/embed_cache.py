"""
Query-embedding cache — the single biggest retrieval cost is embedding the
question (~850ms measured, local or API). The SAME question re-asked (FAQ
phrasing, evaluation runs, retried queries) re-pays it for nothing: the
embedding of a given (model, text) pair never changes, so it is perfectly
cacheable.

Two layers, both optional and never fatal:
    1. in-process dict (LRU-ish, capped)   — ~0ms, per worker
    2. Upstash Redis (chat.cache)          — shared across workers/restarts

Keyed by sha256(model + text) so a model change can never serve stale
vectors. Values are the raw embedding list (JSON in Redis).
"""
from __future__ import annotations

import hashlib
import threading

_MAX_LOCAL = 256                 # ~30KB / entry → a few MB worst case
_local: dict = {}
_lock = threading.Lock()


def _key(model: str, text: str) -> str:
    h = hashlib.sha256(f"{model}\x00{text}".encode()).hexdigest()
    return f"rag:qemb:{h}"


def get(model: str, text: str):
    k = _key(model, text)
    with _lock:
        if k in _local:
            return _local[k]
    from app.services.chat import cache
    v = cache.get_json(k)
    if isinstance(v, list) and v:
        with _lock:
            _local[k] = v
        return v
    return None


def put(model: str, text: str, embedding, ttl: int) -> None:
    if not embedding:
        return
    k = _key(model, text)
    with _lock:
        if len(_local) >= _MAX_LOCAL:      # cheap bound; entries rotate anyway
            _local.clear()
        _local[k] = list(embedding)
    from app.services.chat import cache
    cache.set_json(k, list(embedding), ttl)
