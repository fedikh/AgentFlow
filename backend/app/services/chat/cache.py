"""
Chat cache — Upstash Redis over its REST API. OPTIONAL scalability layer.

PostgreSQL is ALWAYS the source of truth: every write goes to Postgres first
and the cache is invalidated after; reads fall back to Postgres on any miss
or cache error. If the two Upstash env vars are absent the whole module is a
no-op and chat works exactly the same, just without the cache.

.env:
    UPSTASH_REDIS_REST_URL=https://<name>.upstash.io
    UPSTASH_REDIS_REST_TOKEN=<token>

What is cached (and why):
    chat:sessions:{user_id}:{space_id}   the session list a user sees when
                                         opening an agent (TTL 5 min —
                                         invalidated on every mutation, the
                                         TTL is only a safety net)
    chat:messages:{session_id}           the conversation transcript (TTL 1 h
                                         — reloading a chat skips Postgres;
                                         invalidated on every new message)
    chat:activity:{user_id}              last-seen timestamp (TTL 24 h) for
                                         "active users" dashboards

Every call uses a short timeout and swallows failures — a slow or down cache
must never slow down or break the chat itself.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _cfg() -> tuple[str, str]:
    """Credentials come from app settings (.env via pydantic) with a plain
    environment-variable fallback. Read lazily — module-import order must
    not decide whether the cache is on."""
    try:
        from app.config import settings
        url = getattr(settings, "UPSTASH_REDIS_REST_URL", "") or ""
        token = getattr(settings, "UPSTASH_REDIS_REST_TOKEN", "") or ""
    except Exception:
        url, token = "", ""
    url = url or os.getenv("UPSTASH_REDIS_REST_URL") or ""
    token = token or os.getenv("UPSTASH_REDIS_REST_TOKEN") or ""
    return url.rstrip("/"), token


_TIMEOUT = 1.0        # seconds — the cache is an accelerator, never a blocker

SESSIONS_TTL = 300
MESSAGES_TTL = 3600
ACTIVITY_TTL = 86400


def enabled() -> bool:
    url, token = _cfg()
    return bool(url and token)


def _cmd(*args):
    """One Redis command via Upstash REST (POST body = the command array)."""
    url, token = _cfg()
    if not (url and token):
        return None
    try:
        import httpx
        r = httpx.post(url, json=[str(a) for a in args],
                       headers={"Authorization": f"Bearer {token}"},
                       timeout=_TIMEOUT)
        if r.status_code == 200:
            return r.json().get("result")
        logger.debug(f"[CHAT-CACHE] {args[0]} → HTTP {r.status_code}")
    except Exception as e:
        logger.debug(f"[CHAT-CACHE] {args[0]} failed: {e}")
    return None


# ── typed helpers ──────────────────────────────────────────────

def sessions_key(user_id: str, space_id: str) -> str:
    return f"chat:sessions:{user_id}:{space_id}"


def messages_key(session_id: str) -> str:
    return f"chat:messages:{session_id}"


def get_json(key: str):
    raw = _cmd("GET", key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def set_json(key: str, value, ttl: int) -> None:
    try:
        _cmd("SET", key, json.dumps(value, default=str), "EX", int(ttl))
    except Exception:
        pass


def invalidate(*keys: str) -> None:
    if keys:
        _cmd("DEL", *keys)


def incr(key: str, ttl: int):
    """Atomic counter with expiry — used for API rate limiting. Returns the
    new count, or None when the cache is off/unreachable (callers fall back
    to their own limiter)."""
    n = _cmd("INCR", key)
    if n == 1:
        _cmd("EXPIRE", key, int(ttl))
    return n if isinstance(n, int) else None


def touch_activity(user_id: str) -> None:
    """Last-seen marker — lets an admin dashboard count active chat users
    with one KEYS/SCAN, without touching Postgres."""
    _cmd("SET", f"chat:activity:{user_id}",
         datetime.now(timezone.utc).isoformat(), "EX", ACTIVITY_TTL)
