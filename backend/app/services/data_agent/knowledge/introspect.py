"""
Introspection — read the live database's anatomy into AgentFlow's tables.

AgentFlow's catalog (data_source_tables / _columns) is the SOURCE OF TRUTH:
the schema validator checks against it, training reads from it, the UI edits
it. The vector store is a derived index built from it by training.py.

Also collects SAMPLE VALUES of low-cardinality text columns. This is the
step that teaches the model that the department is stored as 'Rh' and not
the 'hr' a user typed — no schema can express that, only the data can.

Runs as a background job (jobs.py) — introspecting a wide schema takes time
and the UI polls for progress.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.services.data_agent import jobs

logger = logging.getLogger(__name__)

# base = the whole schema fits in the prompt (deterministic, no retrieval
# variance). Beyond this, retrieval selects the relevant subset.
BASE_MODE_MAX_TABLES = 40
SAMPLE_MAX_TABLES = 80        # sampling cost guard on very wide schemas
SAMPLE_MAX_COLUMNS = 8        # per table
TEXTY = ("char", "text", "enum", "string", "uuid")


def start_introspection(source_id: str) -> dict:
    return jobs.start_job("introspect", _run, source_id)


def _run(job_id: str, source_id: str):
    from app.database import SessionLocal
    from app.models.data_agent import (DataSource, DataSourceColumn,
                                       DataSourceTable)
    from app.services.data_agent.database import adapter_for, connection

    db = SessionLocal()
    try:
        source = db.query(DataSource).filter(DataSource.id == source_id).first()
        if not source:
            raise RuntimeError("Data source not found")
        adapter = adapter_for(source.dialect)
        whitelist = (json.loads(source.schema_whitelist)
                     if source.schema_whitelist else [])

        jobs.update_job(job_id, step="Connecting…")
        with connection(source) as conn:
            jobs.update_job(job_id, step="Reading schema…")
            snapshot = adapter.introspect(conn, whitelist)

            jobs.update_job(job_id, step="Sampling column values…",
                            total=len(snapshot))
            for i, t in enumerate(snapshot[:SAMPLE_MAX_TABLES]):
                sampled = 0
                for c in t["columns"]:
                    if sampled >= SAMPLE_MAX_COLUMNS or c["pk"]:
                        continue
                    if not any(x in (c["data_type"] or "").lower() for x in TEXTY):
                        continue
                    vals = adapter.sample_values(conn, t["schema"], t["table"],
                                                 c["name"])
                    if vals:
                        c["sample_values"] = vals
                        sampled += 1
                jobs.update_job(job_id, done=i + 1)

        # human edits survive re-introspection, matched on (schema, table)
        previous = {(t.schema_name, t.table_name): t for t in
                    db.query(DataSourceTable)
                    .filter(DataSourceTable.data_source_id == source_id).all()}
        kept = {k: {"description": t.description, "is_enabled": t.is_enabled}
                for k, t in previous.items()}
        for t in previous.values():
            db.delete(t)                          # columns cascade
        db.flush()

        jobs.update_job(job_id, total=len(snapshot), done=0, step="Saving…")
        for i, t in enumerate(snapshot):
            prev = kept.get((t["schema"], t["table"]), {})
            row = DataSourceTable(
                data_source_id=source_id,
                schema_name=t["schema"], table_name=t["table"],
                table_type=t["type"], row_count_estimate=t.get("row_estimate"),
                description=prev.get("description"),
                is_enabled=prev.get("is_enabled", True))
            db.add(row)
            db.flush()
            for c in t["columns"]:
                db.add(DataSourceColumn(
                    table_id=row.id, column_name=c["name"],
                    data_type=c["data_type"], is_nullable=c["nullable"],
                    is_primary_key=c["pk"], foreign_key_ref=c.get("fk_ref"),
                    sample_values=(json.dumps(c["sample_values"])
                                   if c.get("sample_values") else None)))
            jobs.update_job(job_id, done=i + 1)

        source.table_count = len(snapshot)
        source.mode_auto = "base" if len(snapshot) <= BASE_MODE_MAX_TABLES else "rag"
        source.last_introspected_at = datetime.now(timezone.utc)
        if source.status in ("draft", "error"):
            source.status = "connected"
        elif source.status in ("trained", "deployed"):
            source.status = "stale"               # schema moved → re-train
        source.last_error = None
        db.commit()
        return {"tables": len(snapshot), "mode_auto": source.mode_auto}
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


def schema_payload(db, source_id: str) -> list:
    """Tables + columns for the Schema editor."""
    from app.models.data_agent import DataSourceTable
    rows = (db.query(DataSourceTable)
            .filter(DataSourceTable.data_source_id == source_id)
            .order_by(DataSourceTable.schema_name, DataSourceTable.table_name)
            .all())
    return [{
        "id": t.id, "schema": t.schema_name, "table": t.table_name,
        "type": t.table_type, "description": t.description,
        "row_estimate": t.row_count_estimate, "is_enabled": bool(t.is_enabled),
        "columns": [{
            "name": c.column_name, "data_type": c.data_type,
            "nullable": bool(c.is_nullable), "pk": bool(c.is_primary_key),
            "fk_ref": c.foreign_key_ref,
            "sample_values": (json.loads(c.sample_values)
                              if c.sample_values else None),
        } for c in t.columns],
    } for t in rows]
