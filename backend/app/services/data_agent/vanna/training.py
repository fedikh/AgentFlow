"""
Training — build the agent's knowledge base, in the three indexes of the
architecture diagram:

    DDLs        CREATE TABLE per ENABLED table, from the persisted catalog
                (never straight from the live database — human curation and
                the enable toggles must be respected)
    Business    the foreign-key graph · table & column descriptions · sample
                values · glossary terms · uploaded document chunks
    Prompt-SQL  VERIFIED question → SQL pairs only (few-shot examples)

Why the FK graph is a Business document: Vanna has no notion of foreign
keys. Without it, a junction table (order_items, user_departments) is never
semantically similar to the question and the join becomes impossible.

Re-training wipes only schema-derived rows (tag IS NULL) — uploaded document
knowledge survives and is managed by its own panel.
"""
from __future__ import annotations

import json
import logging

from app.services.data_agent import jobs

logger = logging.getLogger(__name__)


def start_training(source_id: str) -> dict:
    return jobs.start_job("train", _run, source_id)


def ddl_for(table) -> str:
    """CREATE TABLE rebuilt from the curated catalog."""
    lines = []
    for c in table.columns:
        line = f"  {c.column_name} {c.data_type}"
        if c.is_primary_key:
            line += " PRIMARY KEY"
        if not c.is_nullable:
            line += " NOT NULL"
        if c.foreign_key_ref:
            line += f" REFERENCES {c.foreign_key_ref}"
        lines.append(line)
    # A bare-name line so the KEYWORD branch can match a literal table name:
    # PostgreSQL's parser indexes "public.users" as a single token, so
    # searching "users" would otherwise miss the DDL it belongs to.
    names = f"-- table: {table.table_name} | {table.schema_name} {table.table_name}"
    header = f"CREATE TABLE {table.schema_name}.{table.table_name} ("
    body = ",\n".join(lines)
    comment = f"\n-- {table.description}" if table.description else ""
    return f"{names}\n{header}\n{body}\n);{comment}"


def _run(job_id: str, source_id: str):
    from app.database import SessionLocal
    from app.models.data_agent import (DataSource, DataSourceExample,
                                       DataSourceGlossary, DataSourceTable)
    from app.services.data_agent.config import KIND_BUSINESS, KIND_DDL, KIND_SQL
    from app.services.data_agent.vanna.client import evict, get_client
    from app.services.data_agent.vanna.store import wipe

    db = SessionLocal()
    try:
        source = db.query(DataSource).filter(DataSource.id == source_id).first()
        if not source:
            raise RuntimeError("Data source not found")
        tables = [t for t in db.query(DataSourceTable)
                  .filter(DataSourceTable.data_source_id == source_id).all()
                  if t.is_enabled]
        if not tables:
            raise RuntimeError("Nothing to train — run introspection first")

        evict(source_id)                       # fresh config, fresh retrieval
        vn = get_client(db, source)

        jobs.update_job(job_id, step="Clearing previous schema knowledge…")
        wipe(db, source, kinds=(KIND_DDL, KIND_SQL, KIND_BUSINESS),
             schema_only=True)                 # documents (tag set) survive

        glossary = (db.query(DataSourceGlossary)
                    .filter(DataSourceGlossary.data_source_id == source_id).all())
        examples = (db.query(DataSourceExample)
                    .filter(DataSourceExample.data_source_id == source_id,
                            DataSourceExample.is_verified.is_(True)).all())
        total = len(tables) + len(glossary) + len(examples) + 1
        jobs.update_job(job_id, total=total, step="Indexing DDLs…", done=0)
        done = 0
        fk_lines: list[str] = []

        # ── index 1: DDLs (+ per-column business notes) ──
        for t in tables:
            vn.add_ddl(ddl_for(t))
            for c in t.columns:
                if c.foreign_key_ref:
                    fk_lines.append(f"{t.schema_name}.{t.table_name}.{c.column_name} "
                                    f"references {c.foreign_key_ref}")
                if c.description:
                    vn.add_documentation(
                        f"Column {t.table_name}.{c.column_name}: {c.description}")
                if c.sample_values:
                    try:
                        vals = json.loads(c.sample_values)
                        vn.add_documentation(
                            f"Column {t.table_name}.{c.column_name} allowed values: "
                            f"{', '.join(map(str, vals))}")
                    except Exception:
                        pass
            if t.description:
                vn.add_documentation(
                    f"Table {t.schema_name}.{t.table_name}: {t.description}")
            done += 1
            jobs.update_job(job_id, done=done)

        # ── index 2: Business — the join map first, it unlocks everything ──
        jobs.update_job(job_id, step="Indexing business knowledge…")
        if fk_lines:
            vn.add_documentation("Foreign key relationships (JOIN paths):\n"
                                 + "\n".join(fk_lines))
        done += 1
        jobs.update_job(job_id, done=done)

        for g in glossary:
            vn.add_documentation(f"{g.term}: {g.definition}")
            done += 1
            jobs.update_job(job_id, done=done)

        # ── index 3: prompt → SQL pairs (verified only) ──
        jobs.update_job(job_id, step="Indexing question → SQL examples…")
        for ex in examples:
            vn.add_question_sql(question=ex.question, sql=ex.sql)
            done += 1
            jobs.update_job(job_id, done=done)

        if source.status != "deployed":        # a live agent stays live
            source.status = "trained"
        source.last_error = None
        db.commit()
        return {"ddls": len(tables), "glossary": len(glossary),
                "examples": len(examples), "fk_relationships": len(fk_lines)}
    except Exception as e:
        db.rollback()
        try:
            source = db.query(DataSource).filter(DataSource.id == source_id).first()
            if source:
                source.status = "error"
                source.last_error = str(e)[:300]
                db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()
