"""
SQLite adapter — a file, not a server. `database` holds the file path;
host/port/user/password are unused.

Opened with mode=ro in the URI so the file is physically read-only for this
connection: the strongest possible guarantee, and the reason SQLite is the
easiest dialect to demo safely.
"""
from __future__ import annotations

from sqlalchemy import text

from .base import DatabaseAdapter


class SQLiteAdapter(DatabaseAdapter):
    name = "sqlite"
    label = "SQLite"
    sqlglot_dialect = "sqlite"
    default_port = 0
    requires_host = False

    def sqlalchemy_url(self, source, password: str) -> str:
        from urllib.parse import quote
        path = (source.database or "").replace("\\", "/")
        return f"sqlite:///file:{quote(path)}?mode=ro&uri=true"

    def connect_args(self, source) -> dict:
        return {"uri": True, "timeout": 8}

    def version_query(self) -> str:
        return "SELECT 'SQLite ' || sqlite_version()"

    def timeout_statements(self, ms: int) -> list[str]:
        return []          # enforced by the driver timeout instead

    def introspect(self, conn, whitelist):
        names = [r[0] for r in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")).fetchall()]
        out = []
        for tbl in names:
            cols = conn.execute(text(f'PRAGMA table_info("{tbl}")')).fetchall()
            fks = {r[3]: f"{r[2]}.{r[4]}" for r in
                   conn.execute(text(f'PRAGMA foreign_key_list("{tbl}")')).fetchall()}
            out.append({
                "schema": "main", "table": tbl, "type": "table",
                "row_estimate": None,
                "columns": [{
                    "name": c[1], "data_type": c[2] or "TEXT",
                    "nullable": not c[3], "pk": bool(c[5]),
                    "fk_ref": fks.get(c[1]),
                } for c in cols],
            })
        return out

    def quote(self, schema: str, table: str) -> str:
        return self.quote_ident(table)          # single-schema database
