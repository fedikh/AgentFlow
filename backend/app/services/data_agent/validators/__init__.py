"""
Validators — the ordered safety chain. NOTHING reaches a customer database
without passing all five checks:

    1. syntax             sqlglot parses it in the source's dialect
    2. single statement    no stacked queries
    3. query type          SELECT only, across the WHOLE AST (CTEs included)
    4. tables & columns    every name exists in the catalog and is enabled
    5. row limit           a bounded result set, injected at the AST level

`validate()` returns the SAFE SQL to execute — callers never execute the
model's string, only what comes back from here.
"""
from __future__ import annotations

from .result import CheckResult, ValidationFailed  # noqa: F401
from .schema_validator import check_tables_and_columns, load_catalog
from .security_validator import apply_row_limit, check_query_type
from .sql_validator import check_single_statement, check_syntax


def validate(db, source, sql: str, adapter=None) -> tuple[str, list]:
    """Run the whole chain. → (safe_sql, [CheckResult…]).
    Raises ValidationFailed with a repair-friendly message on the first
    failing check; the checks already passed are attached to the exception
    by the caller (the validate node)."""
    if adapter is None:
        from app.services.data_agent.database import adapter_for
        adapter = adapter_for(source.dialect)

    checks: list = []
    res, statements = check_syntax(sql, adapter.sqlglot_dialect)
    checks.append(res)
    checks.append(check_single_statement(statements))

    tree = statements[0]
    checks.append(check_query_type(tree))
    checks.append(check_tables_and_columns(tree, load_catalog(db, source)))

    safe_sql, res = apply_row_limit(
        tree, adapter, int(getattr(source, "row_limit", 1000) or 1000))
    checks.append(res)
    return safe_sql, checks
