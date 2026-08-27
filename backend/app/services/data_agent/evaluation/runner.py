"""
Runner — one experiment = every VERIFIED case executed against the agent's
CURRENT configuration (mirror of evaluation/runner.py).

Per case, two executions hit the customer database — the GOLD SQL and the
agent's generated SQL — so the pool stays at 2 workers. Execution accuracy
(result sets compared) is the primary metric; validity, honesty, attempts,
latency and cost complete the picture. One case's failure never kills a run.

Async runs ride the existing jobs.py registry, polled by the UI through
GET /data-sources/jobs/{job_id}.
"""
from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.data_eval import DataEvalCase, DataEvalRun

from .comparison import compare_results

logger = logging.getLogger(__name__)

_WORKERS = 2


# ══════════════════════════════════════════════════════════════
#  Judge — the RAG judge_llm, aimed at a DataSource
# ══════════════════════════════════════════════════════════════

class _JudgeView:
    """DataSource dressed as a RAGSpace for judge_llm: it only reads
    eval_params / judge_api_key_enc (absent → defaults) and the llm_* columns,
    which DataSource shares. Everything else delegates to the source."""
    def __init__(self, source):
        self._s = source
        self.eval_params = None
        self.judge_api_key_enc = None

    def __getattr__(self, k):
        return getattr(self._s, k)


def _build_judge(db, source):
    """→ (judge_llm, label) or (None, "none"). Built fresh per case — langchain
    clients bind their first event loop, and each worker thread has its own."""
    try:
        from app.services.evaluation.scoring.judge import judge_llm
        return judge_llm(db, _JudgeView(source))
    except Exception as e:
        logger.debug(f"[DATA-EVAL/judge] unavailable: {e!r}")
        return None, "none"


def _rows_preview(result: dict, max_rows: int = 5) -> str:
    cols = result.get("columns") or []
    rows = (result.get("rows") or [])[:max_rows]
    head = " | ".join(str(c) for c in cols)
    body = "\n".join(" | ".join(str(v) for v in r) for r in rows)
    more = result.get("row_count", 0) - len(rows)
    return f"{head}\n{body}" + (f"\n… +{more} more row(s)" if more > 0 else "")


# ══════════════════════════════════════════════════════════════
#  One case
# ══════════════════════════════════════════════════════════════

def _stage_ms(timings: dict, prefix: str) -> float | None:
    vals = [v for k, v in (timings or {}).items() if k.startswith(prefix)]
    return round(sum(vals), 1) if vals else None


def _run_case(source_id: str, case: dict, use_judge: bool) -> dict:
    from app.database import SessionLocal
    from app.models.data_agent import DataSource
    from app.services.data_agent.graph import run as run_graph
    from app.services.data_agent.nodes import run_validated

    row = {"question": case["question"], "category": case["category"],
           "difficulty": case["difficulty"], "gold_sql": case["gold_sql"]}
    try:
        # ── gold side ──
        gold_result = None
        if case["gold_sql"]:
            try:
                gold_result = run_validated(source_id, case["gold_sql"])
                row["gold_rows"] = gold_result["row_count"]
            except Exception as e:
                row["gold_error"] = str(e)[:300]

        # ── agent side ──
        t0 = time.perf_counter()
        state = run_graph(source_id, case["question"])
        row["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)

        timings = state.get("timings") or {}
        errors = state.get("errors") or []
        result = state.get("result") or {}
        row.update({
            "sql": state.get("sql"),
            "valid": bool(state.get("valid")),
            "attempts": int(state.get("attempts") or 0),
            "insufficient": bool(state.get("insufficient")),
            "exec_error": state.get("exec_error"),
            "answered_from": state.get("answered_from") or "sql",
            "answer": (state.get("answer") or "")[:500],
            "last_error": (errors[-1].get("message")
                           if errors and isinstance(errors[-1], dict) else None),
            "gen_rows": result.get("row_count"),
            "generate_ms": _stage_ms(timings, "generate") or 0,
            "correct_ms": _stage_ms(timings, "correct"),
            "execute_ms": timings.get("execute"),
            "answer_ms": timings.get("answer"),
        })

        # ── score ──
        if case["category"] == "insufficient":
            honest = bool(state.get("insufficient")) or \
                row["answered_from"] == "documents"
            row["honest"] = 1 if honest else 0
            row["analysis"] = ("✅ refused honestly" if honest
                               else "❌ invented a query instead of refusing")
        elif "gold_error" in row:
            row["analysis"] = "⚠️ gold SQL failed — case not counted"
        elif row["answered_from"] == "documents":
            row["analysis"] = "📄 answered from documents — SQL not comparable"
        elif not result:
            row["match"] = 0
            row["mode"] = "no-result"
            row["detail"] = row.get("exec_error") or row.get("last_error") \
                or ("refused (INSUFFICIENT_SCHEMA)" if row["insufficient"]
                    else "no result")
            row["analysis"] = "❌ produced no result"
        else:
            cmp = compare_results(gold_result, result,
                                  ordered=(case["category"] == "ranking"))
            row.update({"match": cmp["match"], "mode": cmp["mode"],
                        "detail": cmp["detail"]})
            row["analysis"] = (
                "⏸ indeterminate (row cap)" if cmp["match"] is None else
                f"✅ results match ({cmp['mode']})" if cmp["match"] else
                f"❌ results differ ({cmp['mode']})")

        # ── cost estimate ──
        try:
            from app.services.evaluation.scoring.performance import case_cost
            retrieval = state.get("retrieval") or {}
            context = "\n".join(c.get("content", "") for lst in retrieval.values()
                                for c in lst)
            db2 = SessionLocal()
            try:
                src = db2.query(DataSource).filter(DataSource.id == source_id).first()
                model = getattr(src, "llm_model", "") or ""
            finally:
                db2.close()
            row.update(case_cost(case["question"], context,
                                 (row.get("sql") or "") + row["answer"], model))
        except Exception as e:
            logger.debug(f"[DATA-EVAL/cost] {e!r}")

        # ── optional judge on the NL answer ──
        if use_judge and row.get("answer") and "gold_error" not in row \
                and case["category"] != "insufficient" and gold_result:
            db3 = SessionLocal()
            try:
                src = db3.query(DataSource).filter(DataSource.id == source_id).first()
                judge, label = _build_judge(db3, src)
                if judge is not None:
                    from app.services.evaluation.scoring.judge import \
                        judge_correctness
                    expected = case.get("expected_answer") or \
                        f"The correct result is:\n{_rows_preview(gold_result)}"
                    context = _rows_preview(result) if result else "(no result)"
                    score, reason = judge_correctness(
                        judge, case["question"], expected, context, row["answer"])
                    row["correctness"] = score
                    row["judge_reason"] = reason
                    row["judge_label"] = label
            except Exception as e:
                logger.debug(f"[DATA-EVAL/judge] {e!r}")
            finally:
                db3.close()
    except Exception as e:
        row["error"] = str(e)[:300]
        row["analysis"] = "💥 case crashed — see error"
        logger.warning(f"[DATA-EVAL/case] {e!r}")
    return row


# ══════════════════════════════════════════════════════════════
#  Aggregation
# ══════════════════════════════════════════════════════════════

def _avg(rows, key):
    vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))
            and not isinstance(r.get(key), bool)]
    return round(sum(vals) / len(vals), 4) if vals else None


def _rate(rows, pred):
    if not rows:
        return None
    return round(sum(1 for r in rows if pred(r)) / len(rows), 4)


def _recommend(m: dict, per_case: list) -> list:
    rec = []
    acc = (m["accuracy"] or {}).get("execution_accuracy")
    rel = m["reliability"] or {}
    if rel.get("validity_rate") is not None and rel["validity_rate"] < 0.8:
        checks = [r.get("last_error") for r in per_case
                  if r.get("last_error")][:1]
        rec.append("Validity is low — the model writes SQL the validator "
                   "rejects. Inspect the failing checks"
                   + (f" (e.g. “{checks[0][:120]}”)" if checks else "")
                   + " and add verified examples showing the right patterns.")
    if rel.get("insufficient_rate") is not None and rel["insufficient_rate"] > 0.2:
        rec.append("The agent often answers INSUFFICIENT_SCHEMA — enable the "
                   "missing tables, describe them, and add glossary terms for "
                   "the vocabulary these questions use.")
    if acc is not None and acc < 0.7 and (rel.get("validity_rate") or 0) >= 0.8:
        weak = sorted(((c, v.get("execution_accuracy")) for c, v in
                       (m.get("by_category") or {}).items()
                       if v.get("execution_accuracy") is not None),
                      key=lambda x: x[1])[:2]
        cats = ", ".join(c for c, _ in weak) or "the weak categories"
        rec.append(f"SQL is valid but often wrong — add verified question→SQL "
                   f"examples for {cats} (they train the few-shot index) and "
                   "enrich column descriptions.")
    by_cat = m.get("by_category") or {}
    join_acc = (by_cat.get("join") or {}).get("execution_accuracy")
    if join_acc is not None and join_acc < 0.6:
        rec.append("JOIN questions fail most — verify the foreign keys were "
                   "introspected and re-train so the FK map is indexed.")
    if rel.get("avg_attempts") is not None and rel["avg_attempts"] > 1.7:
        rec.append("The correction loop works hard (avg attempts "
                   f"{rel['avg_attempts']}) — a stronger LLM or a higher DDL "
                   "top-k would get more queries right on the first try.")
    perf = m.get("performance") or {}
    if perf.get("avg_execute_ms") is not None and perf["avg_execute_ms"] > 5000:
        rec.append("Execution is slow — lower the row limit or add database "
                   "indexes for the common filters.")
    if perf.get("est_cost_per_query") is not None and perf["est_cost_per_query"] > 0.02:
        rec.append("Cost per question is high — a cheaper model may score "
                   "nearly as well; compare runs after switching.")
    return rec


def _config_snapshot(db: Session, source, judge_label: str) -> dict:
    from app.services.data_agent.versions import _snapshot
    cfg = _snapshot(source)
    cfg.pop("llm_api_key_enc", None)
    cfg.pop("embedding_api_key_enc", None)
    try:
        rp = json.loads(cfg.get("retrieval_params") or "{}")
        rp.pop("reranker_api_key_enc", None)
        cfg["retrieval_params"] = rp
    except Exception:
        cfg["retrieval_params"] = {}
    try:
        cfg["chunk_params"] = json.loads(cfg.get("chunk_params") or "{}")
    except Exception:
        cfg["chunk_params"] = {}
    cfg["dialect"] = source.dialect
    cfg["mode"] = getattr(source, "mode_override", None) or \
        getattr(source, "mode_auto", "base")
    cfg["table_count"] = source.table_count or 0
    cfg["judge"] = judge_label
    return cfg


def run_evaluation(db: Session, source, progress=None) -> dict:
    cases = (db.query(DataEvalCase)
             .filter(DataEvalCase.data_source_id == source.id,
                     DataEvalCase.verified.is_(True))
             .order_by(DataEvalCase.created_at).all())
    if not cases:
        raise HTTPException(400, "No verified test cases — build the dataset first")

    case_dicts = [{"question": c.question, "gold_sql": c.gold_sql,
                   "expected_answer": c.expected_answer,
                   "category": c.category or "filter",
                   "difficulty": c.difficulty or "medium"} for c in cases]

    judge, judge_label = _build_judge(db, source)   # availability probe only
    use_judge = judge is not None

    t0 = time.perf_counter()
    per_case: list = [None] * len(case_dicts)
    done = 0
    with ThreadPoolExecutor(max_workers=min(_WORKERS, len(case_dicts))) as pool:
        futures = {pool.submit(_run_case, source.id, c, use_judge): i
                   for i, c in enumerate(case_dicts)}
        for fut in as_completed(futures):
            i = futures[fut]
            per_case[i] = fut.result()
            done += 1
            if progress:
                progress(done, len(case_dicts), case_dicts[i]["question"])
    duration_ms = int((time.perf_counter() - t0) * 1000)

    # ── denominators ──
    crashed = [r for r in per_case if r.get("error")]
    gold_errors = [r for r in per_case if r.get("gold_error")]
    insufficient_cases = [r for r in per_case
                          if r["category"] == "insufficient" and not r.get("error")]
    doc_fallbacks = [r for r in per_case if r.get("answered_from") == "documents"
                     and r["category"] != "insufficient"]
    scored = [r for r in per_case if r.get("match") is not None]
    indeterminate = [r for r in per_case if "mode" in r
                     and r.get("mode") == "indeterminate"]
    sql_cases = [r for r in per_case
                 if r["category"] != "insufficient" and not r.get("error")
                 and not r.get("gold_error")]

    metrics = {
        "cases": len(per_case),
        "comparable_cases": len(scored),
        "gold_errors": len(gold_errors),
        "indeterminate": len(indeterminate),
        "document_fallbacks": len(doc_fallbacks),
        "crashed": len(crashed),
        "accuracy": {
            "execution_accuracy": _avg(scored, "match"),
            "exact_match_rate": _rate(scored, lambda r: r.get("match") == 1 and
                                      r.get("mode") in ("exact", "scalar",
                                                        "both-empty")),
            "honesty_rate": _avg(insufficient_cases, "honest"),
            "answer_correctness": _avg([r for r in per_case
                                        if r.get("correctness") is not None],
                                       "correctness"),
        },
        "reliability": {
            "validity_rate": _rate(sql_cases, lambda r: r.get("valid")),
            "execution_success_rate": _rate(sql_cases,
                                            lambda r: r.get("gen_rows") is not None),
            "insufficient_rate": _rate(sql_cases, lambda r: r.get("insufficient")),
            "document_fallback_rate": _rate(sql_cases,
                                            lambda r: r.get("answered_from") ==
                                            "documents"),
            "first_try_valid_rate": _rate(sql_cases,
                                          lambda r: r.get("valid") and
                                          (r.get("attempts") or 0) <= 1),
            "avg_attempts": _avg(sql_cases, "attempts"),
        },
        "performance": {
            "avg_total_ms": _avg(per_case, "total_ms"),
            "avg_generate_ms": _avg(per_case, "generate_ms"),
            "avg_execute_ms": _avg(per_case, "execute_ms"),
            "avg_answer_ms": _avg(per_case, "answer_ms"),
            "est_tokens_per_query": _avg(per_case, "est_tokens"),
            "est_cost_per_query": _avg(per_case, "est_cost"),
        },
        "powered_by": {
            "accuracy": "execution accuracy — result sets compared",
            "judge": (per_case and next((r.get("judge_label") for r in per_case
                                         if r.get("judge_label")), None))
            or judge_label or "none",
            "cost": "litellm cost map",
        },
    }

    by_cat: dict = {}
    for r in per_case:
        by_cat.setdefault(r["category"], []).append(r)
    metrics["by_category"] = {
        cat: {
            "cases": len(rows),
            "execution_accuracy": _avg([r for r in rows
                                        if r.get("match") is not None], "match"),
            "validity_rate": _rate([r for r in rows
                                    if r["category"] != "insufficient"],
                                   lambda r: r.get("valid")),
            "avg_attempts": _avg(rows, "attempts"),
        } for cat, rows in by_cat.items()
    }
    metrics["recommendations"] = _recommend(metrics, per_case)

    run = DataEvalRun(
        data_source_id=source.id,
        config_summary=json.dumps(_config_snapshot(db, source, judge_label),
                                  default=str),
        metrics=json.dumps(metrics, default=str),
        results=json.dumps(per_case, default=str),
        num_cases=len(per_case),
        duration_ms=duration_ms)
    db.add(run)
    db.commit()
    db.refresh(run)
    return _run_dict(run, include_results=True)


# ══════════════════════════════════════════════════════════════
#  Async + run history
# ══════════════════════════════════════════════════════════════

def start_run(source_id: str) -> dict:
    from app.services.data_agent import jobs

    def _job(job_id: str, sid: str):
        from app.database import SessionLocal
        from app.models.data_agent import DataSource
        db = SessionLocal()
        try:
            source = db.query(DataSource).filter(DataSource.id == sid).first()
            if not source:
                raise RuntimeError("Data source not found")
            total = (db.query(DataEvalCase)
                     .filter(DataEvalCase.data_source_id == sid,
                             DataEvalCase.verified.is_(True)).count())
            jobs.update_job(job_id, total=total, step="Starting…")

            def progress(done, tot, last):
                jobs.update_job(job_id, done=done, total=tot, step=last)

            return run_evaluation(db, source, progress=progress)
        finally:
            db.close()

    return jobs.start_job("evaluate", _job, source_id)


def _load(raw):
    try:
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _run_dict(run: DataEvalRun, include_results: bool = False) -> dict:
    d = {
        "id": run.id, "data_source_id": run.data_source_id,
        "num_cases": run.num_cases, "duration_ms": run.duration_ms,
        "created_at": str(run.created_at),
        "metrics": _load(run.metrics) or {},
        "config": _load(run.config_summary) or {},
    }
    if include_results:
        d["results"] = _load(run.results) or []
    return d


def list_runs(db: Session, source_id: str, limit: int = 20) -> list:
    rows = (db.query(DataEvalRun)
            .filter(DataEvalRun.data_source_id == source_id)
            .order_by(DataEvalRun.created_at.desc()).limit(limit).all())
    return [_run_dict(r) for r in rows]


def get_run(db: Session, source_id: str, run_id: str) -> dict:
    r = (db.query(DataEvalRun)
         .filter(DataEvalRun.id == run_id,
                 DataEvalRun.data_source_id == source_id).first())
    if not r:
        raise HTTPException(404, "Run not found")
    return _run_dict(r, include_results=True)


def delete_run(db: Session, source_id: str, run_id: str) -> dict:
    r = (db.query(DataEvalRun)
         .filter(DataEvalRun.id == run_id,
                 DataEvalRun.data_source_id == source_id).first())
    if not r:
        raise HTTPException(404, "Run not found")
    db.delete(r)
    db.commit()
    return {"deleted": run_id}
