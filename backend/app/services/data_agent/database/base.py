"""
Database adapters — everything dialect-specific lives here and ONLY here.
Adding a database = one subclass + one registry line; no other module in
data_agent/ may branch on the dialect name.

Each adapter provides four families of behaviour:
    connection   SQLAlchemy URL + driver-specific connect args
    session      read-only enforcement + statement timeout
    introspection tables/columns/PK/FK + low-cardinality sample values
    SQL shaping  AST-level row limit + EXPLAIN dry run (sqlglot dialect)
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod


class DatabaseAdapter(ABC):
    name: str = ""                 # postgres | mysql | mssql | sqlite
    label: str = ""
    sqlglot_dialect: str = ""      # postgres | mysql | tsql | sqlite
    default_port: int = 0
    requires_host: bool = True     # sqlite is a file, not a server

    # ── connection ────────────────────────────────────────────
    def extra(self, source) -> dict:
        try:
            raw = getattr(source, "extra_params", None)
            return json.loads(raw) if isinstance(raw, str) else (raw or {})
        except Exception:
            return {}

    @abstractmethod
    def sqlalchemy_url(self, source, password: str) -> str:
        """Driver URL for create_engine()."""

    def connect_args(self, source) -> dict:
        """Driver kwargs (connect timeouts, TLS…)."""
        return {}

    def version_query(self) -> str:
        return "SELECT version()"

    # ── per-connection safety ─────────────────────────────────
    def readonly_statements(self) -> list[str]:
        """Statements that make THIS session read-only. Defense in depth on
        top of the read-only database account (the primary control)."""
        return []

    def timeout_statements(self, ms: int) -> list[str]:
        """Statements that cap the execution time of THIS session."""
        return []

    # ── introspection ─────────────────────────────────────────
    @abstractmethod
    def introspect(self, conn, whitelist: list[str]) -> list[dict]:
        """→ [{schema, table, type, row_estimate, columns:[{name, data_type,
        nullable, pk, fk_ref}]}] — whitelist empty = all non-system schemas."""

    def sample_values(self, conn, schema: str, table: str, column: str,
                      max_distinct: int = 25) -> list | None:
        """Distinct values of a low-cardinality column (None above the cap).
        Teaches the model the data's real spelling ('Rh', not 'hr').
        Identifiers come from introspection — never from user input."""
        from sqlalchemy import text
        q = self.quote(schema, table)
        col = self.quote_ident(column)
        try:
            rows = conn.execute(text(
                f"SELECT DISTINCT {col} AS v FROM {q} LIMIT {int(max_distinct) + 1}"
            )).fetchall()
        except Exception:
            return None
        vals = [r[0] for r in rows if r[0] is not None]
        return [str(v)[:80] for v in vals] if len(vals) <= max_distinct else None

    # ── identifiers ───────────────────────────────────────────
    def quote_ident(self, ident: str) -> str:
        return '"' + str(ident).replace('"', '""') + '"'

    def quote(self, schema: str, table: str) -> str:
        if not schema:
            return self.quote_ident(table)
        return f"{self.quote_ident(schema)}.{self.quote_ident(table)}"

    # ── SQL shaping ───────────────────────────────────────────
    def apply_row_limit(self, sql: str, limit: int) -> str:
        """AST-level cap — sqlglot renders LIMIT / TOP / FETCH per dialect,
        so this is never string concatenation."""
        import sqlglot
        tree = sqlglot.parse_one(sql, dialect=self.sqlglot_dialect)
        if tree.args.get("limit") is None:
            tree = tree.limit(int(limit))
        return tree.sql(dialect=self.sqlglot_dialect)

    def explain(self, conn, sql: str) -> None:
        """Dry run — raises when the database rejects the query. Catches
        permission and semantic errors at zero data cost."""
        from sqlalchemy import text
        conn.execute(text(f"EXPLAIN {sql}"))
