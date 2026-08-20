"""
CSV import — bulk-load the two hand-written knowledge indexes.

    prompt → SQL pairs   question,sql[,verified]
    glossary             term,definition

Real-world files are messy, so the reader is deliberately tolerant:
  · UTF-8 with or without BOM (Excel writes one)
  · comma OR semicolon delimiters (French Excel writes ';')
  · column names in any order, case-insensitive, with common aliases
    (question/prompt/nl, sql/query/requete, term/terme, definition/meaning)
  · a header-less file is accepted when it has exactly the right column count

Rows that cannot be read are REPORTED, never silently dropped — a partially
imported file with a clear error list is more useful than a mystery.
"""
from __future__ import annotations

import csv
import io
import logging

from fastapi import HTTPException

logger = logging.getLogger(__name__)

MAX_ROWS = 2000

_ALIASES = {
    "question": {"question", "prompt", "nl", "nl_question", "user_question",
                 "demande", "requete_nl"},
    "sql": {"sql", "query", "sql_query", "requete", "requête", "expected_sql"},
    "verified": {"verified", "is_verified", "valide", "validated"},
    "term": {"term", "terme", "mot", "concept", "name"},
    "definition": {"definition", "définition", "meaning", "sens",
                   "description", "explanation"},
}


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _reader(text: str):
    sample = text[:4000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except Exception:
        dialect = csv.excel
        dialect.delimiter = ";" if sample.count(";") > sample.count(",") else ","
    return csv.reader(io.StringIO(text), dialect)


def _map_columns(header: list[str], wanted: list[str]) -> dict:
    """header index per wanted field, or {} when the header isn't recognizable."""
    norm = [(h or "").strip().lower().lstrip("﻿") for h in header]
    mapping = {}
    for field in wanted:
        aliases = _ALIASES[field]
        for i, h in enumerate(norm):
            if h in aliases:
                mapping[field] = i
                break
    return mapping


def _rows(data: bytes, required: list[str],
          optional: list[str] = ()) -> tuple[list[dict], list[str]]:
    text = _decode(data).strip()
    if not text:
        raise HTTPException(400, "The file is empty")
    reader = list(_reader(text))
    if not reader:
        raise HTTPException(400, "No rows found in the file")

    header = reader[0]
    mapping = _map_columns(header, list(required) + list(optional))
    body = reader[1:]
    if not all(f in mapping for f in required):
        # no usable header — accept a header-less file with the exact columns
        if len(header) >= len(required):
            mapping = {f: i for i, f in enumerate(required)}
            body = reader
        else:
            raise HTTPException(
                400, f"Could not find the columns {', '.join(required)} in the "
                     f"file. Header found: {', '.join(header) or '(none)'}")

    out, errors = [], []
    for n, row in enumerate(body, start=2):
        if not any((c or "").strip() for c in row):
            continue
        values = {f: (row[i] or "").strip()
                  for f, i in mapping.items() if i < len(row)}
        missing = [f for f in required if not values.get(f)]
        if missing:
            errors.append(f"line {n}: empty {', '.join(missing)}")
            continue
        out.append(values)
        if len(out) >= MAX_ROWS:
            errors.append(f"stopped at {MAX_ROWS} rows (the file is longer)")
            break
    return out, errors


def _truthy(v) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "y", "oui", "x")


def import_examples(db, source, data: bytes, user_id: str = None) -> dict:
    """CSV → prompt→SQL pairs. Only rows explicitly marked verified are
    trained; everything else lands as a draft for human review."""
    from app.models.data_agent import DataSourceExample

    rows, errors = _rows(data, ["question", "sql"], ["verified"])
    imported = verified = 0
    for r in rows:
        is_verified = _truthy(r.get("verified"))
        db.add(DataSourceExample(
            data_source_id=source.id, question=r["question"], sql=r["sql"],
            is_verified=is_verified, created_by=user_id))
        imported += 1
        verified += 1 if is_verified else 0
    if imported and source.status in ("trained", "deployed") and verified:
        source.status = "stale"
    db.commit()
    return {"imported": imported, "verified": verified, "errors": errors[:20]}


def import_glossary(db, source, data: bytes) -> dict:
    """CSV → glossary terms."""
    from app.models.data_agent import DataSourceGlossary

    rows, errors = _rows(data, ["term", "definition"])
    for r in rows:
        db.add(DataSourceGlossary(data_source_id=source.id, term=r["term"],
                                  definition=r["definition"]))
    if rows and source.status in ("trained", "deployed"):
        source.status = "stale"
    db.commit()
    return {"imported": len(rows), "errors": errors[:20]}


TEMPLATES = {
    "examples": "question,sql,verified\n"
                "How many active users are there?,"
                "\"SELECT COUNT(*) FROM users WHERE status = 'ACTIVE'\",true\n",
    "glossary": "term,definition\n"
                "workers of a department,"
                "\"the users linked to that department through user_departments\"\n",
}
