"""
Evaluation — the INDEPENDENT judge LLM.

The judge scores correctness against the ground truth and writes a
human-readable reason per case. Presets: GPT-5 / Claude Sonnet / Gemini /
same-as-RAG. Key resolution: company provider of that family → server env
key → honest fallback to the space LLM (recorded in the run config).
"""
from __future__ import annotations

from .common import (logger, eval_params, space_llm, fix_reasoning_llm,
                     is_reasoning_model, json_from)

JUDGE_PRESETS = {
    "gpt": {"family": "OPENAI", "model": "gpt-5", "label": "GPT-5"},
    "claude": {"family": "ANTHROPIC", "model": "claude-sonnet-4-5", "label": "Claude Sonnet"},
    "gemini": {"family": "GOOGLE", "model": "gemini-2.5-pro", "label": "Gemini"},
    "same": {"family": "", "model": "", "label": "Same as RAG"},
}


def _key_for_family(db, fam: str):
    """Company provider key of that family, else server env key."""
    import os
    try:
        from app.models.api_provider import ApiProvider
        from app.services.providers_crypto import decrypt_key
        for p in db.query(ApiProvider).all():
            pf = (p.family.value if hasattr(p.family, "value") else str(p.family)).upper()
            if pf == fam and p.api_key_encrypted:
                return decrypt_key(p.api_key_encrypted), (p.base_url or "")
    except Exception as e:
        logger.warning(f"[EVAL] provider lookup failed: {e}")
    env_map = {"OPENAI": "OPENAI_API_KEY", "ANTHROPIC": "ANTHROPIC_API_KEY",
               "GOOGLE": "GOOGLE_API_KEY", "GROQ": "GROQ_API_KEY"}
    return os.environ.get(env_map.get(fam, ""), ""), ""


def judge_llm(db, space, max_tokens=2500):
    """→ (llm, used_label). eval_params: {judge: gpt|claude|gemini|same,
    judge_model: optional override}."""
    ep = eval_params(space)
    choice = (ep.get("judge") or "gpt").lower()
    preset = JUDGE_PRESETS.get(choice, JUDGE_PRESETS["gpt"])
    if choice == "same" or not preset["family"]:
        return space_llm(db, space, max_tokens), "same-as-rag"

    fam = preset["family"]
    model = ep.get("judge_model") or preset["model"]
    if is_reasoning_model(model):
        # reasoning models spend output tokens on internal thinking — give
        # Ragas's verbose verification prompts room to finish
        max_tokens = max(max_tokens, 10000)
    api_key, base_url = _key_for_family(db, fam)
    if not api_key:
        logger.warning(f"[EVAL] no key for judge {fam} — falling back to space LLM")
        return space_llm(db, space, max_tokens), "fallback:same-as-rag"
    from app.services.llm_factory import get_llm
    llm = get_llm(family=fam, model=model, api_key=api_key, base_url=base_url,
                  temperature=0.0, max_tokens=max_tokens)
    return fix_reasoning_llm(llm, fam, model), f"{fam}:{model}"


_CORRECTNESS_PROMPT = """You are an independent evaluation judge. Compare the GENERATED answer
to the GROUND TRUTH for this question. Judge factual agreement, not wording.
Then explain in ONE short human-readable sentence what is right or wrong
(e.g. "The answer mentions internship dates not present in the retrieved context.").
Reply ONLY with JSON: {{"correctness": 0.0-1.0, "reason": "one sentence"}}

QUESTION: {question}
GROUND TRUTH: {expected}
CONTEXT (what was retrieved):
{context}
GENERATED ANSWER: {answer}"""


def judge_correctness(judge, question, expected, context, answer):
    """→ (score 0-1, human-readable reason) or (None, None)."""
    try:
        out = json_from(getattr(judge.invoke(_CORRECTNESS_PROMPT.format(
            question=question,
            expected=expected or "(no ground truth — judge answer quality alone)",
            context=(context or "")[:5000], answer=(answer or "")[:2000],
        )), "content", ""))
        if not isinstance(out, dict):
            return None, None
        score = max(0.0, min(1.0, float(out.get("correctness"))))
        return round(score, 3), str(out.get("reason", ""))[:300]
    except Exception as e:
        logger.warning(f"[EVAL] correctness judge failed: {e}")
        return None, None
