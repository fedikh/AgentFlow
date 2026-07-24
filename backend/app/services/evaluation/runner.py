"""
Evaluation — the experiment runner.

For every case: retrieve (with per-stage timings) → custom retrieval math →
generate the answer → Ragas context/answer scoring (judge fallback) →
independent-judge correctness with a human-readable reason → performance
estimates. Aggregates, per-category breakdown, weighted overall score,
recommendations, config snapshot — saved as one comparable EvalRun.
"""
from __future__ import annotations

import json
import time

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.evaluation import EvalCase, EvalRun
from .common import logger, price_for
from .judge import judge_llm, judge_correctness
from .ragas_engine import ragas_scores, fallback_scores
from .metrics import relevant, retrieval_metrics, avg, overall_score, recommend


def _config_snapshot(db, space, judge_used: str) -> dict:
    rp = {}
    try:
        rp = json.loads(getattr(space, "retrieval_params", None) or "{}")
    except Exception:
        pass
    return {
        "embedding": getattr(space, "embedding_model", ""),
        "chunk_mode": str(getattr(space, "chunk_mode", "")),
        "chunk_strategy": getattr(space, "chunk_strategy", ""),
        "llm": getattr(space, "llm_model", ""),
        "retrieval_profile": rp.get("profile", "balanced"),
        "search_mode": rp.get("search_mode", "hybrid"),
        "rerank": bool(getattr(space, "reranking_enabled", False)),
        "top_k": getattr(space, "top_k", 5),
        "judge": judge_used,
    }


def _case_analysis(row) -> str:
    if row.get("error"):
        return "❌ Case failed to execute."
    if row.get("hit") is None:
        return "ℹ No expected source labeled — retrieval not scored."
    if not row["hit"]:
        return ("❌ Expected document NOT retrieved — raise recall "
                "(High Recall profile, multi-query, check chunking).")
    m = row.get("mrr")
    rank = round(1.0 / m) if m else None
    if rank == 1:
        return "✅ Correct source retrieved and ranked #1."
    return (f"⚠ Correct source retrieved but ranked #{rank} — "
            "enable re-ranking to push it to the top.")


def run_evaluation(db: Session, space, org_id: str) -> dict:
    from app.services.retrieval import retrieve as engine_retrieve

    cases = db.query(EvalCase).filter(EvalCase.rag_space_id == space.id).all()
    if not cases:
        raise HTTPException(400, "No test cases — upload or generate a dataset first")

    judge, judge_used = None, "none"
    try:
        judge, judge_used = judge_llm(db, space)
    except Exception as e:
        logger.warning(f"[EVAL] no judge LLM: {e}")

    in_price, out_price = price_for(getattr(space, "llm_model", ""))
    t0 = time.perf_counter()
    per_case = []
    for case in cases:
        row = {"case_id": case.id, "question": case.question,
               "category": case.category or "semantic",
               "difficulty": case.difficulty or "medium"}
        try:
            t = time.perf_counter()
            r = engine_retrieve(db, space, case.question)
            items = r["items"]
            row["retrieval_ms"] = round((time.perf_counter() - t) * 1000, 1)
            row["timings"] = r.get("timings_ms")

            # 1) retrieval — pure math
            row.update(retrieval_metrics(items, case))
            row["expected"] = {"document": case.expected_document, "page": case.expected_page}
            row["top_sources"] = [
                {"document": it["document"], "page": it["page"], "score": it["score"],
                 "method": it["method"],
                 "relevant": relevant(it, case) if case.expected_document else None}
                for it in items[:5]
            ]

            if judge and items:
                from app.services.llm_factory import generate_answer
                contexts = [f"[{it['document']} p.{it['page']}]\n{it['content']}" for it in items]
                context = "\n\n---\n\n".join(contexts)
                tg = time.perf_counter()
                answer = generate_answer(db, space, case.question, context, "")
                row["answer_ms"] = round((time.perf_counter() - tg) * 1000, 1)
                row["answer"] = (answer or "")[:800]
                tok_in = (len(context) + len(case.question)) // 4
                tok_out = len(answer or "") // 4
                row["est_tokens"] = tok_in + tok_out
                row["est_cost"] = round((tok_in * in_price + tok_out * out_price) / 1e6, 6)

                # 2+3) context & answer — Ragas (fallback: judge single-call)
                scores = ragas_scores(db, space, judge, case.question,
                                      case.expected_answer, contexts, answer)
                if scores is None:
                    scores = fallback_scores(judge, case.question, case.expected_answer,
                                             context, answer)
                row.update(scores)

                # 4) correctness — independent judge + human-readable reason
                corr, reason = judge_correctness(judge, case.question,
                                                 case.expected_answer, context, answer)
                row["correctness"] = corr
                row["reason"] = reason
        except Exception as e:
            row["error"] = str(e)[:300]
            logger.warning(f"[EVAL] case failed: {e}")
        row["analysis"] = _case_analysis(row)
        per_case.append(row)

    labeled = [r for r in per_case if r.get("hit") is not None]
    metrics = {
        "cases": len(per_case),
        "labeled_cases": len(labeled),
        "hit_rate": round(sum(1 for r in labeled if r["hit"]) / len(labeled), 3) if labeled else None,
        "recall_at_k": round(sum(1 for r in labeled if r["hit"]) / len(labeled), 3) if labeled else None,
        "precision_at_k": avg("precision_at_k", per_case),
        "mrr": avg("mrr", per_case),
        "ndcg": avg("ndcg", per_case),
        "context_precision": avg("context_precision", per_case),
        "context_recall": avg("context_recall", per_case),
        "faithfulness": avg("faithfulness", per_case),
        "answer_relevancy": avg("answer_relevancy", per_case),
        "correctness": avg("correctness", per_case),
        "avg_retrieval_ms": avg("retrieval_ms", per_case),
        "avg_answer_ms": avg("answer_ms", per_case),
        "est_tokens_per_query": avg("est_tokens", per_case),
        "est_cost_per_query": avg("est_cost", per_case),
        "powered_by": {
            "retrieval": "custom-math",
            "context_answer": ("ragas" if any(r.get("scored_by") == "ragas" for r in per_case)
                               else "judge-fallback" if any(r.get("scored_by") for r in per_case)
                               else "none"),
            "correctness": judge_used if any(r.get("correctness") is not None for r in per_case) else "none",
        },
    }
    by_cat = {}
    for cat in {r["category"] for r in per_case}:
        rows = [r for r in per_case if r["category"] == cat]
        lab = [r for r in rows if r.get("hit") is not None]
        by_cat[cat] = {
            "cases": len(rows),
            "recall_at_k": round(sum(1 for r in lab if r["hit"]) / len(lab), 3) if lab else None,
            "mrr": avg("mrr", rows),
            "faithfulness": avg("faithfulness", rows),
            "correctness": avg("correctness", rows),
        }
    metrics["by_category"] = by_cat
    metrics.update(overall_score(metrics))
    metrics["recommendations"] = recommend(metrics, space)

    run = EvalRun(
        rag_space_id=space.id,
        config_summary=json.dumps(_config_snapshot(db, space, judge_used)),
        metrics=json.dumps(metrics),
        results=json.dumps(per_case),
        num_cases=len(per_case),
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return _run_dict(run, include_results=True)


def _run_dict(run: EvalRun, include_results: bool = False) -> dict:
    d = {
        "id": run.id,
        "created_at": str(run.created_at),
        "num_cases": run.num_cases,
        "duration_ms": run.duration_ms,
        "config": json.loads(run.config_summary or "{}"),
        "metrics": json.loads(run.metrics or "{}"),
    }
    if include_results:
        d["results"] = json.loads(run.results or "[]")
    return d


def list_runs(db: Session, space_id: str, limit: int = 20) -> list:
    rows = (db.query(EvalRun).filter(EvalRun.rag_space_id == space_id)
            .order_by(EvalRun.created_at.desc()).limit(limit).all())
    return [_run_dict(r) for r in rows]


def get_run(db: Session, space_id: str, run_id: str) -> dict:
    r = db.query(EvalRun).filter(EvalRun.id == run_id,
                                 EvalRun.rag_space_id == space_id).first()
    if not r:
        raise HTTPException(404, "Run not found")
    return _run_dict(r, include_results=True)
