"""
SQL Server adapter — pyodbc + ODBC Driver 18 (optional dependency).

TOP cannot be appended to a query string (it goes after SELECT), which is
exactly why row limiting happens on the sqlglot AST in base.py — never by
concatenation.
"""
from __future__ import annotations

from sqlalchemy import text

from .base import DatabaseAdapter


class MSSQLAdapter(DatabaseAdapter):
    name = "mssql"
    label = "SQL Server"
    sqlglot_dialect = "tsql"
    default_port = 1433

    def sqlalchemy_url(self, source, password: str) -> str:
        from urllib.parse import quote_plus
        extra = self.extra(source)
        driver = extra.get("odbc_driver", "ODBC Driver 18 for SQL Server")
        trust = extra.get("trust_server_certificate", "yes")
        port = source.port or self.default_port
        odbc = (f"DRIVER={{{driver}}};SERVER={source.host},{port};"
                f"DATABASE={source.database};UID={source.username};PWD={password};"
                f"TrustServerCertificate={trust};Connection Timeout=8;")
        return f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc)}"

    def version_query(self) -> str:
        return "SELECT @@VERSION"

    def readonly_statements(self) -> list[str]:
        # T-SQL has no session-level READ ONLY; the read-only login is the
        # control, and the SELECT-only AST guard runs on every statement.
        return []

    def timeout_statements(self, ms: int) -> list[str]:
        return [f"SET LOCK_TIMEOUT {int(ms)}"]

    def quote_ident(self, ident: str) -> str:
        return "[" + str(ident).replace("]", "]]") + "]"

    def sample_values(self, conn, schema, table, column, max_distinct=25):
        q = self.quote(schema, table)
        col = self.quote_ident(column)
        try:
            rows = conn.execute(text(
                f"SELECT DISTINCT TOP {int(max_distinct) + 1} {col} AS v FROM {q}"
            )).fetchall()
        except Exception:
            return None
        vals = [r[0] for r in rows if r[0] is not None]
        return [str(v)[:80] for v in vals] if len(vals) <= max_distinct else None

    def explain(self, conn, sql: str) -> None:
        """SHOWPLAN parses and plans without executing."""
        conn.execute(text("SET SHOWPLAN_ALL ON"))
        try:
            conn.execute(text(sql))
        finally:
            conn.execute(text("SET SHOWPLAN_ALL OFF"))

    def introspect(self, conn, whitelist):
        if whitelist:
            scope, params = "c.TABLE_SCHEMA IN :w", {"w": tuple(whitelist)}
        else:
            scope, params = "c.TABLE_SCHEMA NOT IN ('sys')", {}
        cols = conn.execute(text(f"""
            SELECT c.TABLE_SCHEMA, c.TABLE_NAME, t.TABLE_TYPE,
                   c.COLUMN_NAME, c.DATA_TYPE, c.IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS c
            JOIN INFORMATION_SCHEMA.TABLES t
              ON t.TABLE_SCHEMA = c.TABLE_SCHEMA AND t.TABLE_NAME = c.TABLE_NAME
            WHERE {scope}
            ORDER BY c.TABLE_SCHEMA, c.TABLE_NAME, c.ORDINAL_POSITION"""),
            params).fetchall()

        fks = {(r[0], r[1], r[2]): r[3] for r in conn.execute(text("""
            SELECT s1.name, t1.name, c1.name,
                   s2.name + '.' + t2.name + '.' + c2.name
            FROM sys.foreign_key_columns fkc
            JOIN sys.tables t1 ON t1.object_id = fkc.parent_object_id
            JOIN sys.schemas s1 ON s1.schema_id = t1.schema_id
            JOIN sys.columns c1 ON c1.object_id = t1.object_id
                                AND c1.column_id = fkc.parent_column_id
            JOIN sys.tables t2 ON t2.object_id = fkc.referenced_object_id
            JOIN sys.schemas s2 ON s2.schema_id = t2.schema_id
            JOIN sys.columns c2 ON c2.object_id = t2.object_id
                                AND c2.column_id = fkc.referenced_column_id""")).fetchall()}

        pks = {(r[0], r[1], r[2]) for r in conn.execute(text("""
            SELECT s.name, t.name, c.name
            FROM sys.key_constraints kc
            JOIN sys.tables t ON t.object_id = kc.parent_object_id
            JOIN sys.schemas s ON s.schema_id = t.schema_id
            JOIN sys.index_columns ic ON ic.object_id = t.object_id
                                      AND ic.index_id = kc.unique_index_id
            JOIN sys.columns c ON c.object_id = t.object_id
                               AND c.column_id = ic.column_id
            WHERE kc.type = 'PK'""")).fetchall()}

        tables: dict = {}
        for sch, tbl, ttype, col, dtype, nullable in cols:
            t = tables.setdefault((sch, tbl), {
                "schema": sch, "table": tbl,
                "type": "view" if "VIEW" in str(ttype).upper() else "table",
                "row_estimate": None, "columns": []})
            t["columns"].append({
                "name": col, "data_type": dtype, "nullable": nullable == "YES",
                "pk": (sch, tbl, col) in pks, "fk_ref": fks.get((sch, tbl, col))})
        return list(tables.values())
