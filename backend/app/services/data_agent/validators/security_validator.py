"""
Check 3 — QUERY TYPE (SELECT only), and Check 5 — ROW LIMIT.

The read-only database account is the primary control; this is the
application-level guard that makes a mistake impossible even if that account
is ever over-privileged.

The whole AST is walked, so a DELETE hidden inside a CTE or a subquery is
rejected exactly like a top-level one.
"""
from __future__ import annotations

from sqlglot import exp

from .result import CheckResult, ValidationFailed

# Every node type that writes, changes structure, or grants rights.
FORBIDDEN_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create,
    exp.Grant, exp.TruncateTable, exp.Merge, exp.Command,
)
# Functions/statements that touch the filesystem or the server — banned even
# inside a SELECT (Postgres COPY … PROGRAM, pg_read_file, MySQL INTO OUTFILE).
FORBIDDEN_FUNCTIONS = {
    "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "lo_import",
    "lo_export", "dblink", "xp_cmdshell", "openrowset", "load_file",
}


def check_query_type(tree: exp.Expression) -> CheckResult:
    """SELECT-only, everywhere in the tree."""
    root = tree.this if isinstance(tree, exp.With) else tree
    if not isinstance(root, (exp.Select, exp.Union, exp.Subquery)):
        raise ValidationFailed(
            "query_type",
            f"Only SELECT statements are allowed (got {type(root).__name__.upper()}).")

    for node in tree.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise ValidationFailed(
                "query_type",
                f"Forbidden operation {node.key.upper()} found in the query — "
                "this agent may only read data with SELECT.")
        if isinstance(node, exp.Anonymous):
            name = (node.name or "").lower()
            if name in FORBIDDEN_FUNCTIONS:
                raise ValidationFailed(
                    "query_type", f"Function {name}() is not allowed.")
        if isinstance(node, exp.Into):
            raise ValidationFailed(
                "query_type", "SELECT … INTO is not allowed (it writes data).")
    return CheckResult("query_type", True, "SELECT only")


def apply_row_limit(tree: exp.Expression, adapter, limit: int) -> tuple[str, CheckResult]:
    """Check 5 — guarantee a bounded result set. Rendered through the
    dialect's AST so SQL Server gets TOP and Postgres gets LIMIT."""
    sql = tree.sql(dialect=adapter.sqlglot_dialect)
    existing = tree.args.get("limit")
    if existing is not None:
        try:
            asked = int(existing.expression.name)
            if asked <= int(limit):
                return sql, CheckResult("row_limit", True, f"LIMIT {asked} (model)")
        except Exception:
            pass                       # non-literal limit → re-cap below
    limited = adapter.apply_row_limit(sql, int(limit))
    return limited, CheckResult("row_limit", True, f"capped at {limit}")
