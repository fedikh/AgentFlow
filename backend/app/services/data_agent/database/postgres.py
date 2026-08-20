"""PostgreSQL adapter — psycopg2 (already a project dependency)."""
from __future__ import annotations

from sqlalchemy import text

from .base import DatabaseAdapter


class PostgresAdapter(DatabaseAdapter):
    name = "postgres"
    label = "PostgreSQL"
    sqlglot_dialect = "postgres"
    default_port = 5432

    def sqlalchemy_url(self, source, password: str) -> str:
        from urllib.parse import quote_plus
        user = quote_plus(source.username or "")
        pwd = quote_plus(password or "")
        port = source.port or self.default_port
        return (f"postgresql+psycopg2://{user}:{pwd}@{source.host}:{port}"
                f"/{source.database}")

    def connect_args(self, source) -> dict:
        return {"connect_timeout": 8,
                "sslmode": self.extra(source).get("sslmode", "prefer")}

    def readonly_statements(self) -> list[str]:
        return ["SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY"]

    def timeout_statements(self, ms: int) -> list[str]:
        return [f"SET statement_timeout = {int(ms)}"]

    def introspect(self, conn, whitelist):
        scope = ("AND c.table_schema = ANY(:w)" if whitelist else
                 "AND c.table_schema NOT IN ('pg_catalog','information_schema')")
        cols = conn.execute(text(f"""
            SELECT c.table_schema, c.table_name, t.table_type,
                   c.column_name, c.data_type, c.is_nullable
            FROM information_schema.columns c
            JOIN information_schema.tables t
              ON t.table_schema = c.table_schema AND t.table_name = c.table_name
            WHERE t.table_type IN ('BASE TABLE','VIEW') {scope}
            ORDER BY c.table_schema, c.table_name, c.ordinal_position"""),
            {"w": whitelist} if whitelist else {}).fetchall()

        keys = conn.execute(text("""
            SELECT tc.table_schema, tc.table_name, kcu.column_name,
                   tc.constraint_type,
                   ccu.table_schema || '.' || ccu.table_name || '.' || ccu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON kcu.constraint_name = tc.constraint_name
             AND kcu.table_schema = tc.table_schema
            LEFT JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
             AND tc.constraint_type = 'FOREIGN KEY'
            WHERE tc.constraint_type IN ('PRIMARY KEY','FOREIGN KEY')""")).fetchall()

        counts = {(r[0], r[1]): int(r[2] or 0) for r in conn.execute(text(
            "SELECT schemaname, relname, n_live_tup FROM pg_stat_user_tables")).fetchall()}

        pks, fks = set(), {}
        for sch, tbl, col, ctype, ref in keys:
            if ctype == "PRIMARY KEY":
                pks.add((sch, tbl, col))
            elif ref:
                fks[(sch, tbl, col)] = ref

        tables: dict = {}
        for sch, tbl, ttype, col, dtype, nullable in cols:
            key = (sch, tbl)
            t = tables.setdefault(key, {
                "schema": sch, "table": tbl,
                "type": "view" if ttype == "VIEW" else "table",
                "row_estimate": counts.get(key), "columns": []})
            t["columns"].append({
                "name": col, "data_type": dtype, "nullable": nullable == "YES",
                "pk": (sch, tbl, col) in pks, "fk_ref": fks.get((sch, tbl, col))})
        return list(tables.values())
