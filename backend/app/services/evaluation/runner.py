"""
Evaluation — the experiment runner.

For every case (fanned out over a worker pool — each worker has its own DB
session; the executor is a seam that can be swapped for Celery workers when
the platform gets a broker):

    retrieve (real pipeline, timed) → ranx retrieval metrics →
    generate the answer (space LLM, timed) → Ragas generation metrics
    (judge fallback) → independent-judge correctness + reason →
    litellm cost estimate

Aggregates are grouped in the THREE metric families (retrieval / generation /
performance) with a per-category breakdown and rule-engine recommendations.
There is deliberately NO composite "overall score": any weighting of the
families is arbitrary, and conclusions drawn from a composite inherit that
arbitrariness — the families are reported side by side instead.

Each run stores a FULL config snapshot (embedding, LLM, chunking, retrieval,
judge) so experiments are comparable: change one thing, re-run, diff.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.evaluation import EvalCase, EvalRun
from .common import logger, eval_params
from .scoring import (avg, case_cost, fallback_scores, hit_rate,
                      judge_correctness, judge_llm, ragas_scores, relevant,
                      score_case)

_WORKERS = 3      # parallel cases; swap the executor for Celery to scale out

# In-memory experiment jobs — the frontend polls these for live progress
# (case-by-case counter + percentage). Pruned as jobs finish.
_JOBS: dict = {}
_JOBS_LOCK = threading.Lock()


# ══════════════════════════════════════════════════════════════
#  Config snapshot — the experiment's full RAG configuration
# ══════════════════════════════════════════════════════════════

def _chunking_summary(db, space) -> dict:
    """The REAL chunking config — not just the legacy chunk_strategy column
    (which defaults to 'recursive' and hid the actual setup).

    PER_DOCUMENT → each file name with the strategy that chunked it.
    SINGLE       → the per-format strategy map (pdf → heading, csv → row…)."""
    mode = str(getattr(space, "chunk_mode", "") or "SINGLE").upper()
    if mode == "PER_DOCUMENT":
        from sqlalchemy import text as _t
        rows = db.execute(_t(
            """SELECT file_name, COALESCE(chosen_strategy, chunk_strategy) AS s
               FROM documents WHERE rag_space_id = :sid ORDER BY file_name"""),
            {"sid": space.id}).fetchall()
        return {"mode": "Per document",
                "files": {r.file_name: (r.s or "—") for r in rows}}
    fmt_map = {}
    try:
        raw = getattr(space, "chunk_format_map", None)
        fmt_map = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception:
        pass
    if fmt_map:
        return {"mode": "Single (per format)",
                "strategies": {ft: (v or {}).get("strategy") or "—"
                               for ft, v in fmt_map.items()}}
    return {"mode": "Single",
            "strategies": getattr(space, "chunk_strategy", "") or "recursive"}


def _config_snapshot(db, space, judge_used: str) -> dict:
    rp = {}
    try:
        raw = getattr(space, "retrieval_params", None)
        rp = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception:
        pass
    return {
        "embedding": {
            "model": getattr(space, "embedding_model", ""),
            "provider": str(getattr(space, "embedding_provider", "") or ""),
            "company_provider": bool(getattr(space, "embedding_provider_id", None)),
            "dimensions": getattr(space, "embedding_dim", None),
        },
        "llm": {
            "model": getattr(space, "llm_model", ""),
            "provider": str(getattr(space, "llm_provider", "") or ""),
            "company_provider": bool(getattr(space, "llm_provider_id", None)),
            "temperature": getattr(space, "llm_temperature", 0.2),
            "max_tokens": getattr(space, "llm_max_tokens", 1024),
            "system_prompt": "custom" if getattr(space, "system_prompt", None) else "default",
        },
        "chunking": _chunking_summary(db, space),
        "retrieval": {
            "search_mode": rp.get("search_mode", "hybrid"),
            "top_k": getattr(space, "top_k", 5),
            "rrf_k": rp.get("rrf_k", 60),
            "fetch_k": rp.get("fetch_k", 30),
            "keyword_k": rp.get("keyword_k", 30),
            "query_enhancement": rp.get("transform_enabled", True),
            "reranker": (rp.get("reranker_model") or
                         ("rerank-2.5" if rp.get("reranker_provider") == "voyage"
                          else "BGE v2-m3 (local)")),
            "rerank_top_n": rp.get("rerank_top_n", 10),
        },
        "judge": judge_used,
    }


# ══════════════════════════════════════════════════════════════
#  Per-case analysis + rule-engine recommendations (no AI)
# ══════════════════════════════════════════════════════════════

def _case_analysis(row) -> str:
    if row.get("error"):
        return "❌ Case failed to execute."
    if row.get("hit") is None:
        return "ℹ No expected source labeled — retrieval not scored."
    if not row["hit"]:
        return ("❌ Expected document NOT retrieved — raise recall "
                "(fetch_k / keyword_k, check chunking).")
    m = row.get("mrr")
    rank = round(1.0 / m) if m else None
    if rank == 1:
        return "✅ Correct source retrieved and ranked #1."
    return f"⚠ Correct source retrieved but ranked #{rank} — the re-ranker should lift it."


def _recommend(m: dict, space) -> list:
    """Weak metrics → concrete config actions. Pure rules, no AI."""
    recs = []
    r, g, p = m.get("retrieval", {}), m.get("generation", {}), m.get("performance", {})
    hit, precision = r.get("hit_rate", r.get("recall_at_k")), r.get("precision_at_k")
    faith = g.get("faithfulness")

    if hit is not None and hit < 0.7:
        recs.append("Low hit rate — retrieval misses the right documents: raise fetch_k / "
                    "keyword_k in Advanced, enable query enhancement, or revisit chunking.")
    if hit is not None and hit >= 0.8 and faith is not None and faith < 0.75:
        recs.append("Retrieval works, GENERATION is the problem — tighten the system "
                    "prompt (answer only from context) or use a stronger LLM.")
    if precision is not None and precision < 0.3:
        recs.append("Low precision — much of what is retrieved is noise: lower top_k "
                    "or keep Hybrid mode so the re-ranker gets better candidates.")
    cp, cr = g.get("context_precision"), g.get("context_recall")
    if cp is not None and cp < 0.5:
        recs.append("Low context precision — the LLM reads mostly noise: lower top_k.")
    if cr is not None and cr < 0.6:
        recs.append("Low context recall — needed facts missing from context: raise "
                    "top_k / fetch_k.")
    by_cat = m.get("by_category", {})
    def weak(cat, key="hit_rate", thr=0.6):
        v = by_cat.get(cat, {}).get(key)
        return v is not None and v < thr
    if weak("exact_id") or weak("entity_lookup"):
        recs.append("Weak on identifier/entity lookups — use Hybrid or Keyword search mode.")
    if weak("multilingual"):
        recs.append("Weak multilingual — prefer BGE-M3 embeddings (multilingual) and "
                    "the BGE v2-m3 reranker.")
    lat = (p.get("avg_retrieval_ms") or 0) + (p.get("avg_answer_ms") or 0)
    if lat > 6000:
        recs.append("Slow end-to-end — switch the re-ranker to rerank-2.5 (API) and/or "
                    "disable query enhancement.")
    cost = p.get("est_cost_per_query")
    if cost is not None and cost > 0.02:
        recs.append(f"High estimated cost (${cost:.3f}/query) — consider a cheaper LLM tier.")
    if not recs:
        recs.append("Healthy — no critical issues detected. Compare experiments after config changes.")
    return recs


# ══════════════════════════════════════════════════════════════
#  The run
# ══════════════════════════════════════════════════════════════

def _run_case(space_id: str, case, has_judge: bool, llm_model: str) -> dict:
    """One case, in its own DB session (thread-safe fan-out unit).

    The judge LLM is built FRESH per case: langchain clients cache their async
    connection on the first event loop that uses them, and Ragas creates one
    loop per thread — a judge shared across workers ends up awaiting futures
    "attached to a different loop" and hangs the run."""
    from app.database import SessionLocal
    from app.models.rag_space import RAGSpace

    row = {"case_id": case.id, "question": case.question,
           "category": case.category or "semantic",
           "difficulty": case.difficulty or "medium"}
    db = SessionLocal()
    try:
        space = db.query(RAGSpace).filter(RAGSpace.id == space_id).first()

        judge = None
        if has_judge:
            try:
                judge, _ = judge_llm(db, space)
            except Exception as e:
                logger.warning(f"[EVAL] per-case judge failed: {e}")
        from app.services.retrieval import retrieve as engine_retrieve
        t = time.perf_counter()
        r = engine_retrieve(db, space, case.question)
        items = r["items"]
        row["retrieval_ms"] = round((time.perf_counter() - t) * 1000, 1)
        row["timings"] = r.get("timings_ms")

        # 1) retrieval — ranx (deterministic math), fixed K = the space's
        # Top-K so precision@K means one thing across the whole run
        row.update(score_case(items, case, k=getattr(space, "top_k", 0) or 0))
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

            # 2) performance — litellm cost estimate
            row.update(case_cost(case.question, context, answer, llm_model))

            # 3) generation — Ragas (judge fallback)
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
    finally:
        db.close()
    row["analysis"] = _case_analysis(row)
    return row


def run_evaluation(db: Session, space, org_id: str, progress=None) -> dict:
    """Run the whole dataset. `progress(done, total, last_question)` is called
    after every completed case — the async job path feeds the UI with it."""
    cases = db.query(EvalCase).filter(EvalCase.rag_space_id == space.id).all()
    if not cases:
        raise HTTPException(400, "No test cases — upload or generate a dataset first")

    # Resolve the judge ONCE for the run label; the instance itself is thrown
    # away — every case builds its own (see _run_case: loop-safety).
    judge_used, has_judge = "none", False
    try:
        _probe, judge_used = judge_llm(db, space)
        has_judge = _probe is not None
        del _probe
    except Exception as e:
        logger.warning(f"[EVAL] no judge LLM: {e}")

    llm_model = getattr(space, "llm_model", "") or ""
    t0 = time.perf_counter()

    # fan-out: each case in its own session; executor is the Celery seam.
    # as_completed → per-case progress; original case order is preserved.
    by_idx, done = {}, 0
    with ThreadPoolExecutor(max_workers=min(_WORKERS, len(cases))) as pool:
        futs = {pool.submit(_run_case, space.id, c, has_judge, llm_model): (i, c)
                for i, c in enumerate(cases)}
        for fut in as_completed(futs):
            i, c = futs[fut]
            by_idx[i] = fut.result()
            done += 1
            if progress:
                progress(done, len(cases), (c.question or "")[:100])
    per_case = [by_idx[i] for i in range(len(cases))]

    labeled = [r for r in per_case if r.get("hit") is not None]
    metrics = {
        "cases": len(per_case),
        "labeled_cases": len(labeled),
        "retrieval": {
            "hit_rate": hit_rate(labeled),
            "precision_at_k": avg("precision_at_k", labeled),
            "mrr": avg("mrr", labeled),
            "ndcg": avg("ndcg", labeled),
        },
        "generation": {
            "faithfulness": avg("faithfulness", per_case),
            "answer_relevancy": avg("answer_relevancy", per_case),
            "context_precision": avg("context_precision", per_case),
            "context_recall": avg("context_recall", per_case),
            "correctness": avg("correctness", per_case),
        },
        "performance": {
            "avg_retrieval_ms": avg("retrieval_ms", per_case),
            "avg_answer_ms": avg("answer_ms", per_case),
            "est_tokens_per_query": avg("est_tokens", per_case),
            "est_cost_per_query": avg("est_cost", per_case),
        },
        "powered_by": {
            "retrieval": "ranx",
            "generation": ("ragas" if any(r.get("scored_by") == "ragas" for r in per_case)
                           else "judge-fallback" if any(r.get("scored_by") for r in per_case)
                           else "none"),
            "correctness": judge_used if any(r.get("correctness") is not None for r in per_case) else "none",
            "performance": "litellm cost map",
        },
    }
    by_cat = {}
    for cat in {r["category"] for r in per_case}:
        rows = [r for r in per_case if r["category"] == cat]
        lab = [r for r in rows if r.get("hit") is not None]
        by_cat[cat] = {
            "cases": len(rows),
            "hit_rate": hit_rate(lab),
            "mrr": avg("mrr", lab),
            "faithfulness": avg("faithfulness", rows),
            "correctness": avg("correctness", rows),
        }
    metrics["by_category"] = by_cat
    metrics["recommendations"] = _recommend(metrics, space)

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


# ══════════════════════════════════════════════════════════════
#  Async experiment jobs — live progress for the UI
# ══════════════════════════════════════════════════════════════

def start_evaluation(db: Session, space, org_id: str) -> dict:
    """Kick the experiment off in a background thread and return a job id.
    The frontend polls job_status() for case-by-case progress."""
    total = db.query(EvalCase).filter(EvalCase.rag_space_id == space.id).count()
    if not total:
        raise HTTPException(400, "No test cases — upload or generate a dataset first")

    job_id = str(uuid.uuid4())
    with _JOBS_LOCK:
        # prune: keep at most 5 finished jobs around
        finished = [k for k, v in _JOBS.items() if v["status"] != "running"]
        for k in finished[:-5]:
            _JOBS.pop(k, None)
        _JOBS[job_id] = {"status": "running", "done": 0, "total": total,
                         "last": "", "run": None, "error": None}

    threading.Thread(target=_job_worker, args=(space.id, org_id, job_id),
                     daemon=True).start()
    return {"job_id": job_id, "total": total}


def _job_worker(space_id: str, org_id: str, job_id: str) -> None:
    from app.database import SessionLocal
    from app.models.rag_space import RAGSpace
    db = SessionLocal()
    try:
        space = db.query(RAGSpace).filter(RAGSpace.id == space_id).first()

        def progress(done, total, last):
            j = _JOBS.get(job_id)
            if j:
                j.update(done=done, total=total, last=last)

        run = run_evaluation(db, space, org_id, progress=progress)
        j = _JOBS.get(job_id)
        if j:
            j.update(status="done", run=run)
    except Exception as e:
        logger.warning(f"[EVAL] job {job_id} failed: {e}")
        j = _JOBS.get(job_id)
        if j:
            j.update(status="error", error=str(e)[:300])
    finally:
        db.close()


def job_status(job_id: str) -> dict:
    """Polled by the UI: {status, done, total, last, error, run?}."""
    j = _JOBS.get(job_id)
    if not j:
        raise HTTPException(404, "Experiment job not found")
    out = {"status": j["status"], "done": j["done"], "total": j["total"],
           "last": j["last"], "error": j["error"]}
    if j["status"] == "done":
        out["run"] = j["run"]
    return out


# ══════════════════════════════════════════════════════════════
#  Runs history — the Experiments list
# ══════════════════════════════════════════════════════════════

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
    run = db.query(EvalRun).filter(EvalRun.id == run_id,
                                   EvalRun.rag_space_id == space_id).first()
    if not run:
        raise HTTPException(404, "Run not found")
    return _run_dict(run, include_results=True)
