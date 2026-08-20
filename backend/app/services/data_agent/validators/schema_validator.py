"""
Check 4 — ALLOWED TABLES and ALLOWED COLUMNS.

Every table and column referenced by the query must exist in the agent's
introspected catalog (data_source_tables / _columns) AND be enabled. This is
the check that kills hallucinated columns before execution — and its error
message is the single most valuable input to the correction loop, because it
tells the model exactly which names are real.

Aliases, CTE names and SELECT-list aliases are resolved first so legitimate
SQL is never rejected (an alias in ORDER BY is not a hallucinated column).
"""
from __future__ import annotations

from sqlglot import exp

from .result import CheckResult, ValidationFailed

_MAX_LISTED = 30          # keep repair messages readable for the LLM


def load_catalog(db, source) -> dict[str, set]:
    """{table_name_lower: {column_names_lower}} for ENABLED tables only."""
    from app.models.data_agent import DataSourceTable
    rows = (db.query(DataSourceTable)
            .filter(DataSourceTable.data_source_id == source.id).all())
    catalog: dict[str, set] = {}
    for t in rows:
        if not t.is_enabled:
            continue
        cols = {c.column_name.lower() for c in t.columns}
        catalog[t.table_name.lower()] = cols
        catalog[f"{t.schema_name.lower()}.{t.table_name.lower()}"] = cols
    return catalog


def check_tables_and_columns(tree: exp.Expression, catalog: dict) -> CheckResult:
    if not catalog:
        return CheckResult("schema", True, "no catalog yet — skipped")

    # names that are legal without being physical tables
    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    subquery_aliases = {s.alias.lower() for s in tree.find_all(exp.Subquery)
                        if s.alias}
    virtual = cte_names | subquery_aliases

    # ── tables ──
    alias_to_table: dict[str, str] = {}
    referenced: set[str] = set()
    for tbl in tree.find_all(exp.Table):
        name = tbl.name.lower()
        if name in virtual:
            continue
        qualified = f"{tbl.db.lower()}.{name}" if tbl.db else name
        cols = catalog.get(qualified) or catalog.get(name)
        if cols is None:
            known = ", ".join(sorted({k for k in catalog if "." not in k})[:_MAX_LISTED])
            raise ValidationFailed(
                "schema",
                f"Unknown or disabled table '{tbl.sql()}'. "
                f"Available tables: {known}")
        referenced.add(name)
        if tbl.alias:
            alias_to_table[tbl.alias.lower()] = name

    if not referenced:
        return CheckResult("schema", True, "no physical table referenced")

    # ── columns ──
    select_aliases = {a.alias.lower() for a in tree.find_all(exp.Alias) if a.alias}
    all_allowed = set().union(*(catalog[t] for t in referenced)) | select_aliases

    for col in tree.find_all(exp.Column):
        cname = (col.name or "").lower()
        if not cname or cname == "*":
            continue
        prefix = (col.table or "").lower()
        if prefix:
            if prefix in virtual:
                continue                        # CTE / subquery column
            table = alias_to_table.get(prefix, prefix)
            cols = catalog.get(table)
            if cols is None:
                continue                        # unresolvable alias → skip
            if cname not in cols and cname not in select_aliases:
                listed = ", ".join(sorted(cols)[:_MAX_LISTED])
                raise ValidationFailed(
                    "schema",
                    f"Column '{col.name}' does not exist on table '{table}'. "
                    f"Its columns are: {listed}")
        elif cname not in all_allowed and not virtual:
            listed = ", ".join(sorted(all_allowed)[:_MAX_LISTED])
            raise ValidationFailed(
                "schema",
                f"Column '{col.name}' does not exist on any referenced table "
                f"({', '.join(sorted(referenced))}). Available columns: {listed}")

    return CheckResult("schema", True,
                       f"{len(referenced)} table(s) verified against the catalog")
