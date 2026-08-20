"""
Check 1 — SYNTAX, and Check 2 — SINGLE STATEMENT.

sqlglot parses the SQL in the source's own dialect. This is what catches a
`LIMIT` sent to SQL Server, or a stray markdown fence, BEFORE the database
is ever contacted. Parsing also gives us the AST every later check reads.
"""
from __future__ import annotations

import sqlglot

from .result import CheckResult, ValidationFailed


def check_syntax(sql: str, dialect: str) -> tuple[CheckResult, list]:
    """→ (result, statements). Raises ValidationFailed on a parse error."""
    text = (sql or "").strip()
    if not text:
        raise ValidationFailed("syntax", "The model produced no SQL.")
    try:
        statements = [s for s in sqlglot.parse(text, dialect=dialect) if s]
    except Exception as e:
        raise ValidationFailed(
            "syntax", f"SQL does not parse as {dialect}: {e}")
    return CheckResult("syntax", True, f"parsed as {dialect}"), statements


def check_single_statement(statements: list) -> CheckResult:
    """One question → one statement. Blocks stacked-query injection."""
    if len(statements) != 1:
        raise ValidationFailed(
            "single_statement",
            f"Exactly one statement is allowed, got {len(statements)}.")
    return CheckResult("single_statement", True, "1 statement")
