"""Scoring package — the three metric families, cleanly separated.

    retrieval.py    ranx — deterministic IR math, free (Recall@K, Precision@K,
                    MRR, NDCG)
    generation.py   Ragas (LLM-as-judge framework) — faithfulness,
                    answer_relevancy, context_precision, context_recall
    performance.py  latency + token/cost (litellm cost map) — pure Python
    judge.py        the independent judge LLM (company / local / own key)
"""
from .retrieval import relevant, score_case, avg           # noqa: F401
from .generation import ragas_scores, fallback_scores      # noqa: F401
from .performance import price_for, case_cost              # noqa: F401
from .judge import judge_llm, judge_correctness            # noqa: F401
