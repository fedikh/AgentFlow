"""
Hybrid feedback engine — deterministic detection + constrained LLM diagnosis.

    metrics ──► rule/threshold detector ──► problems (+ allowed actions)
                                                 │
                                     judge LLM (WHY + WHICH allowed action)
                                                 │
                                          structured feedback ──► user

The rules decide WHAT is wrong (cheap, deterministic, no LLM). The LLM only
explains WHY and picks WHAT TO TRY — and it may ONLY choose from a predefined
catalog of allowed configuration changes per problem, so it can never invent
arbitrary config edits. If no judge LLM is available, a deterministic template
produces the same structure. Uses the SAME judge LLM as the evaluation.
"""
from __future__ import annotations

from .common import json_from, logger

# ── the allowed configuration actions (the only vocabulary the LLM may use) ──
ACTION_LABELS = {
    "enable_hybrid_search": "Enable hybrid retrieval (vector + keyword)",
    "increase_top_k": "Increase top_k (keep more retrieved passages)",
    "increase_fetch_k": "Increase fetch_k / keyword_k (more candidates before fusion)",
    "decrease_top_k": "Decrease top_k (less noise in the context)",
    "enable_reranker": "Enable the cross-encoder re-ranker",
    "enable_query_transformation": "Enable query enhancement / transformation",
    "change_embedding_model": "Try a different embedding model",
    "change_chunk_size": "Adjust chunk size / overlap",
    "tighten_system_prompt": "Tighten the system prompt (answer only from context)",
    "use_stronger_llm": "Use a stronger answer LLM",
    "lower_temperature": "Lower the LLM temperature",
    "use_cheaper_llm": "Switch to a cheaper LLM tier",
    "switch_reranker_api": "Switch the re-ranker to the API model (rerank-2.5)",
    "disable_query_enhancement": "Disable query enhancement (reduce latency)",
}

# ── the catalog: problem → family, label, allowed changes ──
CATALOG = {
    "LOW_HIT_RATE": ("retrieval", "Retrieval coverage is weak",
        ["enable_hybrid_search", "increase_fetch_k", "increase_top_k",
         "enable_query_transformation", "change_embedding_model", "change_chunk_size"]),
    "LOW_RANKING": ("retrieval", "Retrieval ranking is weak (right doc not near the top)",
        ["enable_reranker", "enable_hybrid_search", "increase_top_k"]),
    "LOW_PRECISION": ("retrieval", "Retrieved context is noisy (low precision)",
        ["decrease_top_k", "enable_reranker"]),
    "LOW_FAITHFULNESS": ("generation", "Answers are not grounded in the context",
        ["tighten_system_prompt", "use_stronger_llm", "lower_temperature"]),
    "LOW_RELEVANCY": ("generation", "Answers drift from the question",
        ["tighten_system_prompt", "enable_hybrid_search", "enable_reranker"]),
    "LOW_CONTEXT_PRECISION": ("generation", "Most of the retrieved context is irrelevant",
        ["decrease_top_k", "enable_reranker"]),
    "LOW_CONTEXT_RECALL": ("generation", "Needed facts are missing from the context",
        ["increase_top_k", "increase_fetch_k", "change_chunk_size"]),
    "LOW_CORRECTNESS": ("generation", "Final answers are often incorrect",
        ["tighten_system_prompt", "use_stronger_llm", "enable_hybrid_search", "enable_reranker"]),
    "HIGH_LATENCY": ("performance", "End-to-end latency is high",
        ["switch_reranker_api", "disable_query_enhancement", "decrease_top_k"]),
    "HIGH_COST": ("performance", "Estimated cost per query is high",
        ["use_cheaper_llm"]),
}

# ── default thresholds (same spirit as the rule-based recommendations) ──
THRESHOLDS = {
    "hit_rate": 0.70, "mrr": 0.60, "precision_at_k": 0.30,
    "faithfulness": 0.75, "answer_relevancy": 0.75,
    "context_precision": 0.50, "context_recall": 0.60, "correctness": 0.70,
    "latency_ms": 6000, "cost": 0.02,
}


def _fam(metrics, name):
    """Nested (new runs) with a flat-legacy fallback."""
    fam = metrics.get(name)
    if isinstance(fam, dict):
        return fam
    return metrics  # legacy flat runs kept their metrics at the top level


def _pctp(v):
    return "—" if v is None else f"{round(v * 100)}%"


def detect_problems(metrics: dict, thresholds: dict | None = None) -> list:
    """Deterministic: metrics → list of {code, family, label, evidence, allowed}."""
    t = {**THRESHOLDS, **(thresholds or {})}
    r, g, p = _fam(metrics, "retrieval"), _fam(metrics, "generation"), _fam(metrics, "performance")
    hit = r.get("hit_rate", r.get("recall_at_k"))
    out = []

    def add(code, evidence):
        family, label, allowed = CATALOG[code]
        out.append({"code": code, "family": family, "label": label,
                    "evidence": evidence, "allowed": allowed})

    # retrieval
    if hit is not None and hit < t["hit_rate"]:
        add("LOW_HIT_RATE", f"Hit rate@K {_pctp(hit)} (target ≥ {_pctp(t['hit_rate'])})")
    if r.get("mrr") is not None and r["mrr"] < t["mrr"] and (hit is None or hit >= t["hit_rate"]):
        add("LOW_RANKING", f"MRR {_pctp(r['mrr'])}, NDCG {_pctp(r.get('ndcg'))}")
    if r.get("precision_at_k") is not None and r["precision_at_k"] < t["precision_at_k"]:
        add("LOW_PRECISION", f"Precision@K {_pctp(r['precision_at_k'])}")
    # generation
    if g.get("faithfulness") is not None and g["faithfulness"] < t["faithfulness"]:
        add("LOW_FAITHFULNESS", f"Faithfulness {_pctp(g['faithfulness'])}")
    if g.get("answer_relevancy") is not None and g["answer_relevancy"] < t["answer_relevancy"]:
        add("LOW_RELEVANCY", f"Answer relevancy {_pctp(g['answer_relevancy'])}")
    if g.get("context_precision") is not None and g["context_precision"] < t["context_precision"]:
        add("LOW_CONTEXT_PRECISION", f"Context precision {_pctp(g['context_precision'])}")
    if g.get("context_recall") is not None and g["context_recall"] < t["context_recall"]:
        add("LOW_CONTEXT_RECALL", f"Context recall {_pctp(g['context_recall'])}")
    if g.get("correctness") is not None and g["correctness"] < t["correctness"]:
        add("LOW_CORRECTNESS", f"Correctness {_pctp(g['correctness'])}")
    # performance
    lat = (p.get("avg_retrieval_ms") or 0) + (p.get("avg_answer_ms") or 0)
    if lat > t["latency_ms"]:
        add("HIGH_LATENCY", f"~{round(lat)} ms end-to-end")
    cost = p.get("est_cost_per_query")
    if cost is not None and cost > t["cost"]:
        add("HIGH_COST", f"~${cost:.3f} / query")
    return out


def _healthy_families(metrics, problems) -> list:
    """Families with no detected problem — the 'do not change' hints."""
    hit = _fam(metrics, "retrieval").get("hit_rate")
    bad = {p["family"] for p in problems}
    notes = []
    if "generation" not in bad:
        notes.append("Generation looks healthy — don't change the LLM/prompt for these results.")
    if "retrieval" not in bad and hit is not None:
        notes.append("Retrieval looks healthy — no need to change chunking/embedding.")
    return notes


# ── the LLM diagnostic layer (constrained to the allowed actions) ──

_PROMPT = """You are a RAG evaluation analyst. A deterministic engine already \
detected the problems below from the metrics. Your job is ONLY to explain WHY \
each problem likely happens and to recommend WHAT TO TRY — choosing STRICTLY \
from each problem's allowed actions. Never invent other changes.

EVALUATION METRICS:
{metrics}

CURRENT CONFIGURATION:
{config}

DETECTED PROBLEMS (with the ONLY allowed action codes you may recommend):
{problems}

Reply ONLY with JSON of this exact shape:
{{
  "summary": "1-2 sentence overall diagnosis",
  "problems": [
    {{"code": "<problem code>", "why": "1-2 sentences on the likely cause",
      "recommendations": [
        {{"action": "<one of that problem's allowed action codes>",
          "detail": "concrete, e.g. raise top_k from 5 to 10"}}
      ]}}
  ],
  "do_not_change": ["short phrase on what NOT to touch and why"]
}}
Rules: use ONLY the allowed action codes given per problem; 1-3 recommendations \
each; keep it concrete and short. Do not recommend LLM changes when generation \
metrics are healthy."""


def _compact_config(config: dict) -> dict:
    emb = config.get("embedding", {}) or {}
    llm = config.get("llm", {}) or {}
    rt = config.get("retrieval", {}) or {}
    ch = config.get("chunking", {}) or {}
    return {
        "embedding": emb.get("model"),
        "llm": llm.get("model"), "temperature": llm.get("temperature"),
        "chunking": ch.get("mode"),
        "retrieval": rt.get("search_mode"), "top_k": rt.get("top_k"),
        "reranker": rt.get("reranker") if rt.get("reranker") else False,
        "query_enhancement": rt.get("query_enhancement"),
        "rrf_k": rt.get("rrf_k"), "fetch_k": rt.get("fetch_k"), "keyword_k": rt.get("keyword_k"),
    }


def _llm_diagnose(db, space, metrics, config, problems):
    import json
    from .scoring.judge import _invoke_with_retry, judge_llm

    judge, label = judge_llm(db, space, max_tokens=1200)
    if judge is None:
        return None
    prob_lines = "\n".join(
        f"- {p['code']} ({p['label']}): evidence {p['evidence']}; allowed actions: "
        f"{', '.join(p['allowed'])}" for p in problems)
    raw = _invoke_with_retry(judge, _PROMPT.format(
        metrics=json.dumps({k: _fam(metrics, k) for k in ("retrieval", "generation", "performance")}, default=str)[:2000],
        config=json.dumps(_compact_config(config), default=str)[:1000],
        problems=prob_lines))
    data = json_from(raw)
    if not data or "problems" not in data:
        return None
    return {"engine": f"llm:{label}", "judge": label,
            "fallback_same_as_rag": str(label or "").startswith("fallback:"),
            "summary": str(data.get("summary") or "").strip(),
            "problems": _merge(problems, data.get("problems") or []),
            "do_not_change": data.get("do_not_change") or _healthy_families(metrics, problems)}


def _merge(detected: list, llm_problems: list) -> list:
    """Attach the LLM's why/recommendations to the detected problems, keeping
    ONLY allowed actions (guards against the model going off-catalog)."""
    by_code = {p["code"]: p for p in detected}
    llm_by_code = {p.get("code"): p for p in llm_problems}
    out = []
    for code, p in by_code.items():
        lp = llm_by_code.get(code, {})
        recs = []
        for rec in (lp.get("recommendations") or []):
            act = rec.get("action")
            if act in p["allowed"]:
                recs.append({"action": act, "label": ACTION_LABELS.get(act, act),
                             "detail": str(rec.get("detail") or "").strip()})
        if not recs:  # model gave none valid → fall back to the allowed list
            recs = [{"action": a, "label": ACTION_LABELS[a], "detail": ""}
                    for a in p["allowed"][:3]]
        out.append({"code": code, "family": p["family"], "label": p["label"],
                    "evidence": p["evidence"],
                    "why": str(lp.get("why") or "").strip(), "recommendations": recs})
    return out


def _rule_diagnose(metrics, problems):
    """Deterministic fallback — same structure, no LLM."""
    out = []
    for p in problems:
        out.append({"code": p["code"], "family": p["family"], "label": p["label"],
                    "evidence": p["evidence"], "why": "",
                    "recommendations": [{"action": a, "label": ACTION_LABELS[a], "detail": ""}
                                        for a in p["allowed"][:3]]})
    return {"engine": "rules", "judge": None, "fallback_same_as_rag": False,
            "summary": "Detected issues from the metric thresholds.",
            "problems": out, "do_not_change": _healthy_families(metrics, problems)}


def diagnose(db, space, metrics: dict, config: dict) -> dict:
    """Full hybrid feedback: detect (rules) → explain & recommend (LLM, catalog-
    constrained; deterministic fallback)."""
    problems = detect_problems(metrics)
    if not problems:
        return {"status": "healthy", "engine": "rules", "problems": [],
                "summary": "No metric crossed a problem threshold. Compare experiments "
                           "after config changes to keep improving.",
                "do_not_change": []}
    if problems:
        try:
            res = _llm_diagnose(db, space, metrics, config, problems)
            if res:
                res["status"] = "issues"
                return res
        except Exception as e:
            logger.warning(f"[EVAL] LLM diagnosis failed ({e}) — rule fallback")
    res = _rule_diagnose(metrics, problems)
    res["status"] = "issues"
    return res
