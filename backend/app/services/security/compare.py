"""
Campaign comparison — two runs side by side: robustness delta, per-category
change (corrected / regressed), and the config differences between the two
snapshots. Also exposes the corpus listing for the launch screen.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.security import SecurityCase
from .catalog import CATEGORY_META
from .executor import get_run


def list_cases(db: Session) -> dict:
    """The corpus grouped by category (counts for the launch screen)."""
    rows = db.query(SecurityCase).filter(SecurityCase.is_active == True).all()  # noqa: E712
    by_cat = {c: {"label": CATEGORY_META[c]["label"], "desc": CATEGORY_META[c]["desc"],
                  "severity": CATEGORY_META[c]["severity"], "count": 0} for c in CATEGORY_META}
    for r in rows:
        if r.category in by_cat:
            by_cat[r.category]["count"] += 1
    return {"categories": by_cat, "total": len(rows)}


def _cfg_diff(a: dict, b: dict) -> list:
    """Differences between two config snapshots (nested eval-snapshot shape)."""
    fields = [
        ("System prompt", lambda c: c.get("system_prompt_text", ""), True),
        ("LLM", lambda c: (c.get("llm") or {}).get("model"), False),
        ("Temperature", lambda c: (c.get("llm") or {}).get("temperature"), False),
        ("Embedding", lambda c: (c.get("embedding") or {}).get("model"), False),
        ("Top-K", lambda c: (c.get("retrieval") or {}).get("top_k"), False),
        ("Re-ranker", lambda c: (c.get("retrieval") or {}).get("reranker"), False),
        ("Query enhancement", lambda c: (c.get("retrieval") or {}).get("query_enhancement"), False),
    ]
    out = []
    for label, get, is_prompt in fields:
        va, vb = get(a or {}), get(b or {})
        if is_prompt:
            if (va or "").strip() != (vb or "").strip():
                out.append({"field": label, "is_prompt": True})
        elif va != vb:
            out.append({"field": label, "a": va, "b": vb})
    return out


def compare_runs(db: Session, run_a: str, run_b: str) -> dict:
    a = get_run(db, run_a)
    b = get_run(db, run_b)
    ca = (a.get("metrics") or {}).get("by_category", {})
    cb = (b.get("metrics") or {}).get("by_category", {})
    cats = []
    for c in CATEGORY_META:
        sa = ca.get(c)
        sb = cb.get(c)
        if not sa and not sb:
            continue
        ra = sa.get("block_rate") if sa else None
        rb = sb.get("block_rate") if sb else None
        change = None
        if ra is not None and rb is not None:
            change = "corrected" if rb > ra + 1e-9 else "regressed" if rb < ra - 1e-9 else "same"
        cats.append({"category": c, "label": CATEGORY_META[c]["label"],
                     "severity": CATEGORY_META[c]["severity"], "a": ra, "b": rb, "change": change})
    a_snap = a.get("config_snapshot") or {}
    b_snap = b.get("config_snapshot") or {}
    return {
        "a": {"id": a["id"], "score": a.get("robustness_score"),
              "critical_failures": a.get("critical_failures"), "started_at": a.get("started_at"),
              "system_prompt": a_snap.get("system_prompt_text", "")},
        "b": {"id": b["id"], "score": b.get("robustness_score"),
              "critical_failures": b.get("critical_failures"), "started_at": b.get("started_at"),
              "system_prompt": b_snap.get("system_prompt_text", "")},
        "score_delta": (round((b.get("robustness_score") or 0) - (a.get("robustness_score") or 0), 1)
                        if a.get("robustness_score") is not None and b.get("robustness_score") is not None
                        else None),
        "categories": cats,
        "config_diff": _cfg_diff(a.get("config_snapshot"), b.get("config_snapshot")),
    }
