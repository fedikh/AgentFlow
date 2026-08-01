"""
Scoring — generation. Ragas is the LLM-as-judge framework: faithfulness,
answer_relevancy, context_precision and context_recall are computed by Ragas
driving the independent judge LLM (scoring/judge.py) + the space's own
embedder. A single-call judge fallback covers Ragas failures so a run never
breaks; an all-None Ragas result is treated as a failure ("powered by" stays
honest).
"""
from __future__ import annotations

from ..common import logger, json_from

_ASPECTS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]


def ragas_scores(db, space, judge, question, expected, contexts, answer):
    """→ dict of the 4 metrics (+scored_by="ragas"), or None on failure."""
    try:
        from copy import deepcopy
        from ragas import evaluate, EvaluationDataset, SingleTurnSample
        from ragas.run_config import RunConfig
        from ragas.metrics import (faithfulness, answer_relevancy,
                                   context_precision, context_recall)
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from app.services.embedding_factory.resolver import resolve_embedding_config
        from app.services.embedding_factory.factory import get_embedder

        conf = resolve_embedding_config(db, space)
        emb = get_embedder(conf["family"], conf["model"], conf.get("api_key", ""),
                           conf.get("base_url", ""))
        sample = SingleTurnSample(
            user_input=question, response=answer or "",
            retrieved_contexts=[c[:3000] for c in contexts][:8],
            reference=expected or (answer or "")[:500],
        )
        result = evaluate(
            EvaluationDataset(samples=[sample]),
            # deepcopy: the imported metrics are module-level SINGLETONS and
            # cases run in parallel threads — sharing them races the llm/
            # embeddings assignment ("llm must be set to compute score")
            metrics=[deepcopy(faithfulness), deepcopy(answer_relevancy),
                     deepcopy(context_precision), deepcopy(context_recall)],
            llm=LangchainLLMWrapper(judge),
            embeddings=LangchainEmbeddingsWrapper(emb),
            # hard budget: a slow/rate-limited metric errors out instead of
            # hanging the whole experiment (the fallback scorer takes over)
            run_config=RunConfig(timeout=90, max_retries=2),
            show_progress=False,
        )
        row = result.to_pandas().iloc[0].to_dict()

        def g(*names):
            for nm in names:
                v = row.get(nm)
                if v is not None and v == v:
                    return round(float(v), 3)
            return None
        scores = {
            "faithfulness": g("faithfulness"),
            "answer_relevancy": g("answer_relevancy"),
            "context_precision": g("context_precision", "llm_context_precision_with_reference"),
            "context_recall": g("context_recall"),
        }
        # every metric NaN → all internal jobs failed → treat as a failure so
        # the caller falls back and "powered by" stays honest
        if all(v is None for v in scores.values()):
            logger.warning("[EVAL] ragas returned no scores (all jobs failed) — fallback")
            return None
        scores["scored_by"] = "ragas"
        return scores
    except Exception as e:
        logger.warning(f"[EVAL] ragas scoring failed ({e}) — native fallback")
        return None


_FALLBACK_PROMPT = """You are a strict RAG evaluation judge. Score 0.0-1.0:
- faithfulness: every claim in the ANSWER is supported by the CONTEXT.
- answer_relevancy: the ANSWER directly and completely addresses the QUESTION.
- context_precision: fraction of the CONTEXT that is useful for this question.
- context_recall: the CONTEXT contains ALL info needed for the EXPECTED answer.
Reply ONLY with JSON: {{"faithfulness": x, "answer_relevancy": x, "context_precision": x, "context_recall": x}}

QUESTION: {question}
EXPECTED ANSWER: {expected}
CONTEXT:
{context}
ANSWER: {answer}"""


def fallback_scores(judge, question, expected, context, answer):
    """Single judge call scoring the same 4 aspects — used when Ragas fails."""
    try:
        from .judge import _invoke_with_retry
        out = json_from(_invoke_with_retry(judge, _FALLBACK_PROMPT.format(
            question=question, expected=expected or "(none)",
            context=(context or "")[:6000], answer=(answer or "")[:2000],
        )))
        if not isinstance(out, dict):
            return {}
        res = {}
        for k in _ASPECTS:
            try:
                res[k] = max(0.0, min(1.0, float(out.get(k))))
            except Exception:
                res[k] = None
        res["scored_by"] = "judge-fallback"
        return res
    except Exception:
        return {}
