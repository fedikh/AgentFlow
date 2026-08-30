"""
RAG Observability — production monitoring of DEPLOYED spaces, backed by
Langfuse.

Two halves:

  INGEST   every end-user question answered by a deployed agent becomes one
           Langfuse trace (fire-and-forget, off the request path):
               trace  rag-query   input/output · user · session · tags
               span   retrieval   latency · chunks · strategy · top-k
               gen    generation  model · latency · est. tokens & cost
           Uses Langfuse's public ingestion API directly (basic auth) — no
           SDK dependency, and a failure can never break a user's chat.

  SERVE    the in-app dashboard aggregates the traces back FROM Langfuse
           (requests, errors, latency avg/P95/P99, tokens & cost, retrieval
           behavior, per-day series, trace list + details), and completes the
           picture with the platform's own latest evaluation run (quality)
           and security campaign (robustness). Every trace links out to
           Langfuse for the full waterfall.

Configuration (backend/.env):
    LANGFUSE_PUBLIC_KEY=pk-lf-…
    LANGFUSE_SECRET_KEY=sk-lf-…
    LANGFUSE_HOST=https://cloud.langfuse.com   (or a self-hosted URL)

Aggregation notes: numbers are computed from the metadata WE stamp on each
trace (timings, est tokens/cost), so the dashboard works even for models
Langfuse has no price entry for. Estimates use the chars/4 ≈ tokens rule and
litellm's price map — the same convention as the evaluation module.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

logger = logging.getLogger(__name__)

_TIMEOUT = (5, 30)              # connect, read — Langfuse Cloud can be slow
_SHIP_TIMEOUT = 10              # ingestion runs on a background thread
_MAX_PAGES = 5                  # aggregation fetch cap: 5 × 100 traces
_PAGE_SIZE = 100


# ══════════════════════════════════════════════════════════════
#  Configuration
# ══════════════════════════════════════════════════════════════

def _cfg(name: str, default: str = "") -> str:
    """Settings first (pydantic loads backend/.env), env var as fallback —
    pydantic does NOT export .env values into os.environ."""
    try:
        from app.config import settings
        v = getattr(settings, name, None)
        if v:
            return str(v)
    except Exception:
        pass
    return os.getenv(name) or default


def _host() -> str:
    return _cfg("LANGFUSE_HOST", "https://cloud.langfuse.com").rstrip("/")


def _keys() -> tuple[str, str]:
    return (_cfg("LANGFUSE_PUBLIC_KEY"), _cfg("LANGFUSE_SECRET_KEY"))


def enabled() -> bool:
    pk, sk = _keys()
    return bool(pk and sk)


def status() -> dict:
    return {"configured": enabled(), "host": _host() if enabled() else None}


def _auth():
    pk, sk = _keys()
    return (pk, sk)


def trace_url(trace_id: str, project_id: str = None) -> str:
    """Deep link to the trace. With the projectId (returned by the traces
    API) we build the exact UI path — the universal /trace/{id} resolver
    depends on the viewer's session and fails while a fresh trace is still
    being processed."""
    if project_id:
        return f"{_host()}/project/{project_id}/traces/{trace_id}"
    return f"{_host()}/trace/{trace_id}"


# ══════════════════════════════════════════════════════════════
#  INGEST — one trace per answered question
# ══════════════════════════════════════════════════════════════

def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _est_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)


def _est_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    try:
        from app.services.evaluation.scoring.performance import price_for
        pin, pout = price_for(model or "")
        return round((tokens_in * pin + tokens_out * pout) / 1_000_000, 6)
    except Exception:
        return 0.0


def _resolved_llm(db, space) -> tuple[str | None, str | None]:
    """The EFFECTIVE provider/model — resolved through the same factory path
    the space uses to call the LLM. The raw llm_provider column is stale when
    a company provider or an own key is configured."""
    try:
        from app.services.llm_factory.resolver import resolve_llm_config
        conf = resolve_llm_config(db, space)
        return (conf.get("family") or getattr(space, "llm_provider", None),
                conf.get("model") or getattr(space, "llm_model", None))
    except Exception as e:
        logger.debug(f"[OBS] llm resolution failed: {e!r}")
        return (getattr(space, "llm_provider", None),
                getattr(space, "llm_model", None))


def record_query(space, user, question: str, answer: str, sources: list,
                 timings: dict, session_id: str = None,
                 error: str = None, db=None) -> None:
    """Fire-and-forget: build the trace and ship it on a daemon thread."""
    if not enabled():
        return
    try:
        provider, model = (_resolved_llm(db, space) if db is not None
                           else (getattr(space, "llm_provider", None),
                                 getattr(space, "llm_model", None)))
        payload = _build_batch(space, user, question, answer, sources or [],
                               timings or {}, session_id, error,
                               provider, model)
    except Exception as e:
        logger.debug(f"[OBS] trace build failed: {e!r}")
        return
    threading.Thread(target=_ship, args=(payload,), daemon=True).start()


def _build_batch(space, user, question, answer, sources, timings,
                 session_id, error, provider=None, model=None) -> dict:
    now = datetime.now(timezone.utc)
    total_ms = float(timings.get("total_ms") or 0)
    retrieval_ms = float(timings.get("retrieval_ms") or 0)
    answer_ms = float(timings.get("answer_ms") or 0)
    start = now - timedelta(milliseconds=total_ms)

    provider = provider or getattr(space, "llm_provider", None)
    model = model or getattr(space, "llm_model", None)
    context_chars = sum(len(s.get("content") or "") for s in sources)
    tok_in = _est_tokens(question) + context_chars // 4
    tok_out = _est_tokens(answer)
    cost = _est_cost(model or "", tok_in, tok_out)

    trace_id = str(uuid.uuid4())
    rp = {}
    try:
        rp = json.loads(getattr(space, "retrieval_params", None) or "{}")
    except Exception:
        pass

    meta = {
        "space_id": space.id, "space_name": space.name,
        "department_id": getattr(space, "department_id", None),
        "total_ms": total_ms, "retrieval_ms": retrieval_ms,
        "answer_ms": answer_ms,
        "chunks": len(sources), "tokens_in": tok_in, "tokens_out": tok_out,
        "tokens": tok_in + tok_out, "est_cost": cost,
        "model": model,
        "provider": provider,
        "search_mode": rp.get("search_mode") or "hybrid",
        "top_k": getattr(space, "top_k", None),
        "reranker": rp.get("reranker_provider") or "bge",
        "error": error,
    }

    def ev(etype, body):
        return {"id": str(uuid.uuid4()), "type": etype,
                "timestamp": _iso(now), "body": body}

    batch = [ev("trace-create", {
        "id": trace_id, "name": "rag-query", "timestamp": _iso(start),
        "userId": getattr(user, "email", None) or getattr(user, "id", None),
        "sessionId": session_id,
        "input": {"question": question[:1000]},
        "output": {"answer": (answer or "")[:1500], "error": error},
        "tags": [f"space:{space.id}", "rag-production"],
        "metadata": meta,
    })]
    if retrieval_ms:
        batch.append(ev("span-create", {
            "id": str(uuid.uuid4()), "traceId": trace_id, "name": "retrieval",
            "startTime": _iso(start),
            "endTime": _iso(start + timedelta(milliseconds=retrieval_ms)),
            "metadata": {"chunks": len(sources),
                         "search_mode": meta["search_mode"],
                         "top_k": meta["top_k"], "reranker": meta["reranker"],
                         "stages": timings.get("stages") or {}},
        }))
    if answer_ms or answer:
        gen_start = start + timedelta(milliseconds=retrieval_ms)
        batch.append(ev("generation-create", {
            "id": str(uuid.uuid4()), "traceId": trace_id, "name": "generation",
            "startTime": _iso(gen_start),
            "endTime": _iso(gen_start + timedelta(milliseconds=answer_ms)),
            "model": meta["model"],
            "usage": {"input": tok_in, "output": tok_out, "unit": "TOKENS"},
            "metadata": {"provider": meta["provider"], "est_cost": cost},
            "output": (answer or "")[:1500],
        }))
    return {"batch": batch}


def _ship(payload: dict) -> None:
    try:
        import requests
        r = requests.post(f"{_host()}/api/public/ingestion",
                          json=payload, auth=_auth(), timeout=_SHIP_TIMEOUT)
        if r.status_code >= 300:
            logger.warning(f"[OBS] ingestion {r.status_code}: {r.text[:200]}")
    except Exception as e:
        logger.warning(f"[OBS] ingestion failed: {e!r}")


def _get(path: str, params: dict = None):
    """GET against the Langfuse API — one silent retry on a timeout, then a
    clean HTTP error instead of a raw exception (the UI shows the message)."""
    import requests
    url = f"{_host()}{path}"
    for attempt in (1, 2):
        try:
            r = requests.get(url, params=params, auth=_auth(),
                             timeout=_TIMEOUT)
            break
        except requests.exceptions.Timeout:
            if attempt == 2:
                raise HTTPException(
                    504, "Langfuse is responding slowly — try again in a "
                         "few seconds")
            logger.warning("[OBS] Langfuse timed out — retrying once")
        except requests.exceptions.RequestException as e:
            raise HTTPException(502, f"Langfuse is unreachable: "
                                     f"{str(e)[:120]}")
    if r.status_code >= 300:
        raise HTTPException(502, f"Langfuse answered {r.status_code} — "
                                 "check the keys and host")
    return r


# ══════════════════════════════════════════════════════════════
#  SERVE — aggregation for the in-app dashboard
# ══════════════════════════════════════════════════════════════

def _require_configured():
    if not enabled():
        raise HTTPException(409, "Langfuse is not configured — set "
                                 "LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY "
                                 "(and optionally LANGFUSE_HOST) in the "
                                 "backend environment")


def _fetch_traces(space_id: str, days: int, cap: int = _MAX_PAGES * _PAGE_SIZE) -> list:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    out, page = [], 1
    while len(out) < cap and page <= _MAX_PAGES:
        r = _get("/api/public/traces",
                 {"tags": f"space:{space_id}", "limit": _PAGE_SIZE,
                  "page": page, "fromTimestamp": _iso(since)})
        data = r.json().get("data") or []
        out.extend(data)
        if len(data) < _PAGE_SIZE:
            break
        page += 1
    return out


def _num(meta: dict, key: str) -> float | None:
    v = (meta or {}).get(key)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _percentile(vals: list, p: float):
    if not vals:
        return None
    vs = sorted(vals)
    i = min(len(vs) - 1, max(0, round(p * (len(vs) - 1))))
    return round(vs[i], 1)


def _quality_snapshot(db, space_id: str) -> dict | None:
    """Latest evaluation run → the generation-quality family."""
    try:
        from app.models.evaluation import EvalRun
        run = (db.query(EvalRun).filter(EvalRun.rag_space_id == space_id)
               .order_by(EvalRun.created_at.desc()).first())
        if not run:
            return None
        m = json.loads(run.metrics or "{}")
        gen = m.get("generation") or {}
        ret = m.get("retrieval") or {}
        return {"faithfulness": gen.get("faithfulness"),
                "answer_relevancy": gen.get("answer_relevancy"),
                "context_precision": gen.get("context_precision"),
                "correctness": gen.get("correctness"),
                "hit_rate": ret.get("hit_rate"),
                "cases": m.get("cases"),
                "at": str(run.created_at)}
    except Exception as e:
        logger.debug(f"[OBS] quality snapshot: {e!r}")
        return None


def _security_snapshot(db, space_id: str) -> dict | None:
    """Latest finished security campaign → robustness."""
    try:
        from app.models.security import SecurityRun
        run = (db.query(SecurityRun)
               .filter(SecurityRun.space_id == space_id,
                       SecurityRun.status == "done")
               .order_by(SecurityRun.started_at.desc()).first())
        if not run:
            return None
        return {"robustness_score": run.robustness_score,
                "critical_failures": run.critical_failures or 0,
                "at": str(run.finished_at or run.started_at)}
    except Exception as e:
        logger.debug(f"[OBS] security snapshot: {e!r}")
        return None


def overview(db, space, days: int = 7) -> dict:
    _require_configured()
    days = max(1, min(int(days or 7), 90))
    traces = _fetch_traces(space.id, days)

    metas = [t.get("metadata") or {} for t in traces]
    lat = [v for v in (_num(m, "total_ms") for m in metas) if v]
    ret_lat = [v for v in (_num(m, "retrieval_ms") for m in metas) if v]
    gen_lat = [v for v in (_num(m, "answer_ms") for m in metas) if v]
    toks = [v for v in (_num(m, "tokens") for m in metas) if v]
    costs = [v for v in (_num(m, "est_cost") for m in metas) if v is not None]
    chunks = [v for v in (_num(m, "chunks") for m in metas) if v is not None]
    errors = sum(1 for m in metas if m.get("error"))
    zero_ctx = sum(1 for v in chunks if v == 0)
    n = len(traces)
    avg = lambda vs: round(sum(vs) / len(vs), 1) if vs else None  # noqa: E731

    # per-day series (requests · avg latency · cost)
    by_day: dict = {}
    for t, m in zip(traces, metas):
        day = str(t.get("timestamp") or "")[:10]
        if not day:
            continue
        d = by_day.setdefault(day, {"requests": 0, "lat": [], "cost": 0.0,
                                    "errors": 0})
        d["requests"] += 1
        v = _num(m, "total_ms")
        if v:
            d["lat"].append(v)
        d["cost"] += _num(m, "est_cost") or 0
        if m.get("error"):
            d["errors"] += 1
    series = [{"day": day, "requests": d["requests"],
               "avg_ms": avg(d["lat"]), "cost": round(d["cost"], 5),
               "errors": d["errors"]}
              for day, d in sorted(by_day.items())]

    rp = {}
    try:
        rp = json.loads(getattr(space, "retrieval_params", None) or "{}")
    except Exception:
        pass

    return {
        "days": days,
        "requests": n,
        "errors": errors,
        "error_rate": round(errors / n, 4) if n else None,
        "latency": {"avg_ms": avg(lat), "p50_ms": _percentile(lat, 0.5),
                    "p95_ms": _percentile(lat, 0.95),
                    "p99_ms": _percentile(lat, 0.99),
                    "avg_retrieval_ms": avg(ret_lat),
                    "avg_generation_ms": avg(gen_lat)},
        "tokens": {"total": int(sum(toks)) if toks else 0,
                   "avg_per_request": avg(toks)},
        "cost": {"total": round(sum(costs), 5) if costs else 0,
                 "avg_per_request": round(sum(costs) / len(costs), 6)
                 if costs else None},
        "retrieval": {"avg_chunks": avg(chunks), "zero_context": zero_ctx,
                      "search_mode": rp.get("search_mode") or "hybrid",
                      "top_k": getattr(space, "top_k", None),
                      "reranker": rp.get("reranker_provider") or "bge"},
        "llm": {"model": getattr(space, "llm_model", None),
                "provider": getattr(space, "llm_provider", None)},
        "quality": _quality_snapshot(db, space.id),
        "security": _security_snapshot(db, space.id),
        "series": series,
        "langfuse_host": _host(),
    }


def trace_list(space, days: int = 7, limit: int = 50) -> dict:
    _require_configured()
    traces = _fetch_traces(space.id, max(1, min(int(days or 7), 90)),
                           cap=max(1, min(int(limit or 50), 200)))
    rows = []
    for t in traces:
        m = t.get("metadata") or {}
        q = ((t.get("input") or {}).get("question")
             if isinstance(t.get("input"), dict) else None)
        a = ((t.get("output") or {}).get("answer")
             if isinstance(t.get("output"), dict) else None)
        rows.append({
            "answer": (a or "")[:800],
            "id": t.get("id"),
            "time": t.get("timestamp"),
            "question": (q or "")[:200],
            "latency_ms": _num(m, "total_ms"),
            "retrieval_ms": _num(m, "retrieval_ms"),
            "generation_ms": _num(m, "answer_ms"),
            "tokens": _num(m, "tokens"),
            "cost": _num(m, "est_cost"),
            "chunks": _num(m, "chunks"),
            "error": m.get("error"),
            "user": t.get("userId"),
            "langfuse_url": trace_url(t.get("id"), t.get("projectId")),
        })
    rows.sort(key=lambda r: r["time"] or "", reverse=True)
    return {"traces": rows}


def trace_detail(trace_id: str) -> dict:
    _require_configured()
    t = _get(f"/api/public/traces/{trace_id}").json()
    spans = []
    for o in t.get("observations") or []:
        spans.append({
            "name": o.get("name"), "type": o.get("type"),
            "start": o.get("startTime"), "end": o.get("endTime"),
            "model": o.get("model"),
            "usage": o.get("usage"),
            "metadata": o.get("metadata"),
        })
    return {
        "id": t.get("id"), "time": t.get("timestamp"),
        "user": t.get("userId"), "session": t.get("sessionId"),
        "input": t.get("input"), "output": t.get("output"),
        "metadata": t.get("metadata"),
        "spans": spans,
        "langfuse_url": trace_url(t.get("id"), t.get("projectId")),
    }
