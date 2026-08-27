"""
Dataset generation — the agent's own LLM proposes question→SQL cases from
the introspected catalog (the native path of evaluation/datasets/generator.py;
Ragas is document-oriented so it has no role here).

Every proposal is immediately dry-run through the validated executor: a case
whose gold SQL doesn't even run is stored with the error in gold_note.
ALL generated cases start verified=False — a human confirms the gold SQL in
the UI before the case counts in a run. The ground truth must be human-owned.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.services.evaluation.common import json_from, space_llm

from .cases import CATEGORIES, _case_dict

logger = logging.getLogger(__name__)

_MAX_TABLES_PER_PROMPT = 4
_PROMPT = """You write TEST CASES for a natural-language-to-SQL agent on a
{dialect} database. Here is the relevant schema:

{schema}
{glossary}
Write {n} test cases as a JSON array. Each item:
{{"question": "...", "sql": "...", "category": "...", "difficulty": "easy|medium|hard", "language": "en|fr"}}

Rules:
- "question" is what a business user would really ask, in natural language.
- "sql" is the CORRECT single read-only SELECT that answers it — use ONLY the
  tables and columns above. No INSERT/UPDATE/DELETE/DDL.
- Mix categories from: {categories}.
- Prefer questions with small, deterministic results (counts, aggregates,
  top-N with ORDER BY + LIMIT) over ones returning many rows.
- Answer with the JSON array only."""


def _schema_context(db: Session, source, max_tables: int) -> tuple[str, str]:
    """(schema DDLs, glossary block) — grouped around FK-linked tables so the
    LLM can propose realistic JOIN questions."""
    from app.models.data_agent import DataSourceGlossary, DataSourceTable
    from app.services.data_agent.vanna.training import ddl_for

    tables = [t for t in db.query(DataSourceTable)
              .filter(DataSourceTable.data_source_id == source.id).all()
              if t.is_enabled]
    if not tables:
        return "", ""

    # seed with the most-referenced tables, then pull their FK neighbours
    by_name = {t.table_name.lower(): t for t in tables}
    picked, seen = [], set()

    def push(t):
        if t.id not in seen and len(picked) < max_tables:
            seen.add(t.id)
            picked.append(t)

    ranked = sorted(tables, key=lambda t: -(t.row_count_estimate or 0))
    for t in ranked:
        push(t)
        for c in t.columns:
            if c.foreign_key_ref:
                ref = c.foreign_key_ref.split(".")
                ref_name = (ref[-2] if len(ref) >= 2 else ref[0]).lower()
                if ref_name in by_name:
                    push(by_name[ref_name])
        if len(picked) >= max_tables:
            break

    schema = "\n\n".join(ddl_for(t) for t in picked)
    terms = (db.query(DataSourceGlossary)
             .filter(DataSourceGlossary.data_source_id == source.id)
             .limit(10).all())
    glossary = ""
    if terms:
        glossary = ("\nBusiness vocabulary:\n" +
                    "\n".join(f"- {g.term}: {g.definition}" for g in terms) + "\n")
    return schema, glossary


def generate_cases(db: Session, source, n: int = 8) -> dict:
    """→ {"cases": [...], "engine": "llm"}. Proposals are stored unverified;
    a dry-run result (or error) lands in gold_note for the reviewer."""
    from app.models.data_eval import DataEvalCase
    from app.services.data_agent.nodes import run_validated

    n = max(1, min(int(n or 8), 15))
    schema, glossary = _schema_context(db, source, _MAX_TABLES_PER_PROMPT)
    if not schema:
        return {"cases": [], "engine": "llm",
                "error": "No enabled tables — introspect the database first"}

    llm = space_llm(db, source, max_tokens=2200)
    prompt = _PROMPT.format(dialect=source.dialect, schema=schema,
                            glossary=glossary, n=n,
                            categories=", ".join(c for c in CATEGORIES
                                                 if c != "insufficient"))
    try:
        reply = llm.invoke(prompt).content
    except Exception as e:
        logger.warning(f"[DATA-EVAL/generate] LLM call failed: {e!r}")
        return {"cases": [], "engine": "llm", "error": str(e)[:200]}

    proposals = json_from(reply) or []
    if isinstance(proposals, dict):
        proposals = proposals.get("cases") or []

    out = []
    for p in proposals[:n]:
        if not isinstance(p, dict):
            continue
        q = str(p.get("question") or "").strip()
        sql = str(p.get("sql") or "").strip()
        if not q or not sql:
            continue
        cat = str(p.get("category") or "filter").lower()
        note = None
        try:
            r = run_validated(source.id, sql)
            note = f"dry-run ok · {r['row_count']} row(s)"
        except Exception as e:
            note = f"dry-run failed: {str(e)[:200]}"
        c = DataEvalCase(
            data_source_id=source.id, question=q, gold_sql=sql,
            category=cat if cat in CATEGORIES else "filter",
            difficulty=str(p.get("difficulty") or "medium").lower(),
            language=(str(p.get("language") or "").strip() or None),
            source="generated", verified=False, gold_note=note)
        db.add(c)
        out.append(c)
    db.commit()
    for c in out:
        db.refresh(c)
    return {"cases": [_case_dict(c) for c in out], "engine": "llm"}
