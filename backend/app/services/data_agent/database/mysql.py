"""MySQL / MariaDB adapter — pymysql (optional dependency)."""
from __future__ import annotations

from sqlalchemy import text

from .base import DatabaseAdapter

_SYSTEM = ("mysql", "sys", "information_schema", "performance_schema")


class MySQLAdapter(DatabaseAdapter):
    name = "mysql"
    label = "MySQL"
    sqlglot_dialect = "mysql"
    default_port = 3306

    def sqlalchemy_url(self, source, password: str) -> str:
        from urllib.parse import quote_plus
        user = quote_plus(source.username or "")
        pwd = quote_plus(password or "")
        port = source.port or self.default_port
        return (f"mysql+pymysql://{user}:{pwd}@{source.host}:{port}"
                f"/{source.database}?charset=utf8mb4")

    def connect_args(self, source) -> dict:
        return {"connect_timeout": 8}

    def version_query(self) -> str:
        return "SELECT VERSION()"

    def readonly_statements(self) -> list[str]:
        return ["SET SESSION TRANSACTION READ ONLY"]

    def timeout_statements(self, ms: int) -> list[str]:
        # MySQL ≥ 5.7.8; MariaDB uses max_statement_time (seconds) — both are
        # best-effort, the manager swallows failures.
        return [f"SET SESSION MAX_EXECUTION_TIME = {int(ms)}"]

    def quote_ident(self, ident: str) -> str:
        return "`" + str(ident).replace("`", "``") + "`"

    def introspect(self, conn, whitelist):
        if whitelist:
            scope = "c.table_schema IN :w"
            params = {"w": tuple(whitelist)}
        else:
            scope = "c.table_schema NOT IN :sys"
            params = {"sys": _SYSTEM}
        cols = conn.execute(text(f"""
            SELECT c.table_schema, c.table_name, t.table_type,
                   c.column_name, c.data_type, c.is_nullable, c.column_key,
                   t.table_rows
            FROM information_schema.columns c
            JOIN information_schema.tables t
              ON t.table_schema = c.table_schema AND t.table_name = c.table_name
            WHERE {scope}
            ORDER BY c.table_schema, c.table_name, c.ordinal_position"""),
            params).fetchall()

        fks = {(r[0], r[1], r[2]): r[3] for r in conn.execute(text("""
            SELECT table_schema, table_name, column_name,
                   CONCAT(referenced_table_schema, '.', referenced_table_name,
                          '.', referenced_column_name)
            FROM information_schema.key_column_usage
            WHERE referenced_table_name IS NOT NULL""")).fetchall()}

        tables: dict = {}
        for sch, tbl, ttype, col, dtype, nullable, colkey, rows in cols:
            t = tables.setdefault((sch, tbl), {
                "schema": sch, "table": tbl,
                "type": "view" if "VIEW" in str(ttype).upper() else "table",
                "row_estimate": int(rows or 0), "columns": []})
            t["columns"].append({
                "name": col, "data_type": dtype, "nullable": nullable == "YES",
                "pk": colkey == "PRI", "fk_ref": fks.get((sch, tbl, col))})
        return list(tables.values())
