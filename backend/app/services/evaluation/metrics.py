"""
Evaluation — CUSTOM MATH metrics (no AI, no opinion) + the weighted overall
score + the rule-engine recommendations.

Retrieval: Recall@K / Precision@K / MRR / NDCG from labeled expected sources.
Overall score: 40% retrieval + 40% generation + 20% performance, stored WITH
its breakdown so the UI can show exactly how the number was built.
"""
from __future__ import annotations

import math


def relevant(item, case) -> bool:
    if not case.expected_document:
        return False
    if case.expected_document.lower() not in (item.get("document") or "").lower():
        return False
    if case.expected_page is not None:
        return case.expected_page == item.get("page")
    return True


def retrieval_metrics(items, case) -> dict:
    if not case.expected_document:
        return {"hit": None, "precision_at_k": None, "mrr": None, "ndcg": None}
    ranks = [i + 1 for i, it in enumerate(items) if relevant(it, case)]
    hit = bool(ranks)
    return {
        "hit": hit,
        "precision_at_k": round(len(ranks) / len(items), 3) if items else 0.0,
        "mrr": round(1.0 / ranks[0], 3) if hit else 0.0,
        # single gold label → NDCG = DCG/IDCG = 1/log2(1+rank)
        "ndcg": round(1.0 / math.log2(1 + ranks[0]), 3) if hit else 0.0,
    }


def avg(key, rows):
    vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    return round(sum(vals) / len(vals), 3) if vals else None


def overall_score(m: dict) -> dict:
    """40% retrieval + 40% generation + 20% performance, with breakdown."""
    def part(vals):
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    retrieval = part([m.get("recall_at_k"), m.get("context_recall")])
    generation = part([m.get("faithfulness"), m.get("correctness")])
    lat = (m.get("avg_retrieval_ms") or 0) + (m.get("avg_answer_ms") or 0)
    lat_score = None if not lat else round(max(0.0, min(1.0, (8000 - lat) / 6500)), 3)
    cost = m.get("est_cost_per_query")
    cost_score = None if cost is None else round(max(0.0, min(1.0, (0.05 - cost) / 0.048)), 3)
    performance = part([lat_score, cost_score])

    weights = {"retrieval": 0.4, "generation": 0.4, "performance": 0.2}
    parts = {"retrieval": retrieval, "generation": generation, "performance": performance}
    active = {k: w for k, w in weights.items() if parts[k] is not None}
    total_w = sum(active.values()) or 1.0
    score = sum(parts[k] * w for k, w in active.items()) / total_w
    return {
        "overall_score": round(score * 100),
        "breakdown": {
            "retrieval": {"weight": 40, "score": retrieval,
                          "parts": {"recall_at_k": m.get("recall_at_k"),
                                    "context_recall": m.get("context_recall")}},
            "generation": {"weight": 40, "score": generation,
                           "parts": {"faithfulness": m.get("faithfulness"),
                                     "correctness": m.get("correctness")}},
            "performance": {"weight": 20, "score": performance,
                            "parts": {"latency_ms": round(lat) if lat else None,
                                      "cost_per_query": cost}},
        },
    }


def recommend(m: dict, space) -> list:
    """Rule engine — weak metrics → concrete config actions. No AI."""
    recs = []
    by_cat = m.get("by_category", {})
    recall, precision, faith = m.get("recall_at_k"), m.get("precision_at_k"), m.get("faithfulness")

    def weak(cat, key="recall_at_k", thr=0.6):
        v = by_cat.get(cat, {}).get(key)
        return v is not None and v < thr

    if recall is not None and recall < 0.7:
        recs.append("Low recall — retrieval misses the right chunks: raise fetch_k "
                    "(High Recall profile), enable multi-query, try semantic/heading "
                    "chunking, or a stronger embedding model.")
    if recall is not None and recall >= 0.8 and faith is not None and faith < 0.75:
        recs.append("Retrieval works, GENERATION is the problem — tighten the system "
                    "prompt (answer only from context), reduce context size, or use a "
                    "stronger LLM.")
    if weak("exact_id") or weak("entity_lookup"):
        recs.append("Weak on identifier/entity lookups — keep Exact match + BM25 "
                    "enabled (Hybrid search mode).")
    if weak("table") or weak("structured_data") or weak("aggregation"):
        recs.append("Weak on table/structured questions — use row/table-aware chunking "
                    "for CSV/Excel and enable Metadata retrieval.")
    if weak("multi_hop") or weak("multi_doc"):
        recs.append("Weak on multi-hop questions — enable Multi-query and raise top_k "
                    "so evidence from several documents fits in context.")
    if weak("multilingual"):
        recs.append("Weak multilingual — prefer BGE-M3 / Gemini embeddings and the "
                    "BGE v2-m3 reranker (multilingual).")
    if precision is not None and precision < 0.3 and not getattr(space, "reranking_enabled", False):
        recs.append("Low precision — enable Re-ranking to push the right chunks to the top.")
    cp = m.get("context_precision")
    if cp is not None and cp < 0.5:
        recs.append("Low context precision — much of the context is noise: lower top_k, "
                    "enable re-ranking with a score threshold, or compress context.")
    cr = m.get("context_recall")
    if cr is not None and cr < 0.6:
        recs.append("Low context recall — needed facts are missing from context: raise "
                    "top_k/fetch_k and enable parent retrieval (Full Section).")
    lat = (m.get("avg_retrieval_ms") or 0) + (m.get("avg_answer_ms") or 0)
    if lat > 6000:
        recs.append("Slow end-to-end — Fast profile, FlashRank reranker, or a lighter LLM.")
    cost = m.get("est_cost_per_query")
    if cost is not None and cost > 0.02:
        recs.append(f"High estimated cost (${cost:.3f}/query) — consider a cheaper LLM "
                    "tier or smaller context for this workload.")
    if not recs:
        recs.append("Healthy — no critical issues detected. Compare runs after config changes.")
    return recs
