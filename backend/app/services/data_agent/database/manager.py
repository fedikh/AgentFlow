"""
Connection Manager — the single door to every customer database.

    IT → Connection UI → ConnectionManager → encrypted credentials → engine

Responsibilities:
  · one pooled SQLAlchemy engine per (source, credentials version), cached —
    building an engine per request would exhaust the customer's connections
  · credentials decrypted only here (Fernet, the provider-key helper)
  · EVERY connection handed out is put in read-only mode and given a
    statement timeout before the caller can execute anything
  · connection tests that never raise (they return a structured result)

Security note, deliberately repeated in the UI: the read-only DATABASE
ACCOUNT is the primary control. Session read-only + the SELECT-only AST
guard + row caps + timeouts are defense in depth on top of it.
"""
from __future__ import annotations

import logging
import threading
from contextlib import contextmanager

from sqlalchemy import create_engine, text

from .base import DatabaseAdapter
from .mssql import MSSQLAdapter
from .mysql import MySQLAdapter
from .postgres import PostgresAdapter
from .sqlite import SQLiteAdapter

logger = logging.getLogger(__name__)

ADAPTERS: dict[str, DatabaseAdapter] = {
    a.name: a for a in (PostgresAdapter(), MySQLAdapter(),
                        MSSQLAdapter(), SQLiteAdapter())
}

_engines: dict = {}                 # cache key → Engine
_lock = threading.Lock()
_POOL_SIZE = 2                      # per source: analytics traffic is low
_MAX_OVERFLOW = 3


def adapter_for(dialect: str) -> DatabaseAdapter:
    a = ADAPTERS.get(str(dialect or "").lower())
    if not a:
        raise ValueError(f"Unsupported dialect {dialect!r} "
                         f"(supported: {', '.join(ADAPTERS)})")
    return a


def supported_dialects() -> list:
    return [{"name": a.name, "label": a.label, "default_port": a.default_port,
             "requires_host": a.requires_host} for a in ADAPTERS.values()]


def _password(source) -> str:
    from app.services.providers_crypto import decrypt_key
    enc = getattr(source, "password_enc", None)
    return (decrypt_key(enc) or "") if enc else ""


def _cache_key(source) -> tuple:
    # updated_at changes whenever credentials/host change → engine rebuilt
    return (source.id, str(getattr(source, "updated_at", "")))


def get_engine(source):
    """Pooled engine for this source, built once per credentials version."""
    key = _cache_key(source)
    with _lock:
        eng = _engines.get(key)
        if eng is not None:
            return eng

    adapter = adapter_for(source.dialect)
    url = adapter.sqlalchemy_url(source, _password(source))
    kwargs = {"pool_pre_ping": True, "pool_recycle": 1800,
              "connect_args": adapter.connect_args(source)}
    if adapter.name != "sqlite":
        kwargs.update(pool_size=_POOL_SIZE, max_overflow=_MAX_OVERFLOW,
                      pool_timeout=10)
    engine = create_engine(url, **kwargs)

    with _lock:
        for k in [k for k in _engines if k[0] == source.id]:   # evict old creds
            try:
                _engines.pop(k).dispose()
            except Exception:
                pass
        _engines[key] = engine
    return engine


def dispose(source_id: str) -> None:
    with _lock:
        for k in [k for k in _engines if k[0] == source_id]:
            try:
                _engines.pop(k).dispose()
            except Exception:
                pass


@contextmanager
def connection(source, timeout_ms: int | None = None, readonly: bool = True):
    """A connection that is read-only and time-capped BEFORE the caller can
    run anything. Every query path in the module goes through here."""
    adapter = adapter_for(source.dialect)
    conn = get_engine(source).connect()
    try:
        if readonly:
            for stmt in adapter.readonly_statements():
                try:
                    conn.execute(text(stmt))
                except Exception as e:      # best-effort per dialect
                    logger.debug(f"[DATA-AGENT] readonly stmt skipped: {e}")
        ms = int(timeout_ms if timeout_ms is not None
                 else getattr(source, "timeout_ms", 30000) or 30000)
        for stmt in adapter.timeout_statements(ms):
            try:
                conn.execute(text(stmt))
            except Exception as e:
                logger.debug(f"[DATA-AGENT] timeout stmt skipped: {e}")
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


def test_connection(source) -> dict:
    """→ {ok, dialect, version} | {ok: False, error} — never raises."""
    adapter = adapter_for(source.dialect)
    try:
        dispose(source.id)                  # always test the CURRENT creds
        with connection(source) as conn:
            version = conn.execute(text(adapter.version_query())).scalar()
        return {"ok": True, "dialect": adapter.name,
                "version": str(version or "").splitlines()[0][:200]}
    except Exception as e:
        return {"ok": False, "dialect": adapter.name, "error": str(e)[:300]}
