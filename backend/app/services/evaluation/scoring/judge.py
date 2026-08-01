"""
Scoring — the INDEPENDENT judge LLM.

The judge grades the RAG's answers, so it must NOT be the RAG's own LLM
(a model grading itself inflates scores). The IT configures it exactly like
the other LLM sources — three options, stored in space.eval_params:

    {"judge_source": "company", "judge_provider_id": "...", "judge_model": "..."}
    {"judge_source": "local",   "judge_model": "llama3.1:8b"}
    {"judge_source": "own",     "judge_family": "OPENAI", "judge_model": "gpt-5"}

    company → an admin-deployed LLM provider (api_providers key)
    local   → the local Ollama daemon (free, no key)
    own     → the IT's own key, encrypted per space (judge_api_key_enc)

Fallbacks stay honest: a missing/broken judge config falls back to the
space's own LLM and the run records "fallback:same-as-rag" so scores are
never silently self-graded. Legacy presets ({"judge": "gpt"|...}) keep
working.
"""
from __future__ import annotations

import os
import time

from ..common import (logger, eval_params, space_llm, fix_reasoning_llm,
                      is_reasoning_model, json_from)


def _invoke_with_retry(llm, prompt: str, tries: int = 3) -> str:
    """invoke() with backoff on provider rate limits (429 / TPM) — parallel
    cases + Ragas can momentarily exhaust a key's tokens-per-minute quota."""
    for attempt in range(tries):
        try:
            return getattr(llm.invoke(prompt), "content", "") or ""
        except Exception as e:
            msg = str(e)
            if attempt < tries - 1 and ("429" in msg or "rate_limit" in msg.lower()
                                        or "rate limit" in msg.lower()):
                wait = 4 * (attempt + 1)
                logger.info(f"[EVAL] judge rate-limited — retrying in {wait}s")
                time.sleep(wait)
                continue
            raise

# Legacy presets ({"judge": "gpt"}) — kept so old spaces keep evaluating
_LEGACY_PRESETS = {
    "gpt": {"family": "OPENAI", "model": "gpt-5"},
    "claude": {"family": "ANTHROPIC", "model": "claude-sonnet-4-5"},
    "gemini": {"family": "GOOGLE", "model": "gemini-2.5-pro"},
}

_ENV_KEYS = {"OPENAI": "OPENAI_API_KEY", "ANTHROPIC": "ANTHROPIC_API_KEY",
             "GOOGLE": "GOOGLE_API_KEY", "GROQ": "GROQ_API_KEY"}


def _build(family: str, model: str, api_key: str, base_url: str, max_tokens: int):
    from app.services.llm_factory import get_llm
    if is_reasoning_model(model):
        # reasoning models spend output tokens on internal thinking — give
        # Ragas's verbose verification prompts room to finish
        max_tokens = max(max_tokens, 10000)
    llm = get_llm(family=family, model=model, api_key=api_key,
                  base_url=base_url, temperature=0.0, max_tokens=max_tokens)
    return fix_reasoning_llm(llm, family, model)


def judge_llm(db, space, max_tokens: int = 2500):
    """→ (llm, used_label). Resolves the configured judge source; any failure
    falls back to the space LLM with an honest label."""
    ep = eval_params(space)
    source = (ep.get("judge_source") or "").lower()

    # legacy {"judge": "gpt"|"claude"|"gemini"|"same"}
    if not source and ep.get("judge"):
        choice = str(ep["judge"]).lower()
        if choice == "same":
            return space_llm(db, space, max_tokens), "same-as-rag"
        preset = _LEGACY_PRESETS.get(choice)
        if preset:
            source, ep = "own", {**ep, "judge_family": preset["family"],
                                 "judge_model": ep.get("judge_model") or preset["model"]}

    try:
        if source == "company":
            return _company_judge(db, ep, max_tokens)
        if source == "local":
            model = ep.get("judge_model") or "llama3.1:8b"
            return _build("OLLAMA", model, "", "", max_tokens), f"OLLAMA:{model}"
        if source == "own":
            return _own_judge(db, space, ep, max_tokens)
    except Exception as e:
        logger.warning(f"[EVAL] judge '{source}' unavailable ({e}) — space LLM fallback")
        return space_llm(db, space, max_tokens), "fallback:same-as-rag"

    # nothing configured: first company LLM provider that is NOT the RAG's
    # own provider, else env keys, else the space LLM (honest label)
    try:
        return _default_judge(db, space, max_tokens)
    except Exception as e:
        logger.warning(f"[EVAL] no independent judge available ({e})")
        return space_llm(db, space, max_tokens), "fallback:same-as-rag"


def _company_judge(db, ep, max_tokens):
    from app.models.api_provider import ApiProvider
    from app.services.providers_crypto import decrypt_key
    p = db.query(ApiProvider).filter(ApiProvider.id == ep.get("judge_provider_id")).first()
    if not p or not p.api_key_encrypted:
        raise RuntimeError("judge provider missing or keyless")
    fam = p.family.value if hasattr(p.family, "value") else str(p.family)
    model = ep.get("judge_model") or ""
    if not model:
        from app.services.provider_models import models_for_family
        catalog = models_for_family(fam)
        model = catalog[0]["id"] if catalog else ""
    return (_build(fam, model, decrypt_key(p.api_key_encrypted), p.base_url or "", max_tokens),
            f"company:{p.name}:{model}")


def _own_judge(db, space, ep, max_tokens):
    fam = (ep.get("judge_family") or "OPENAI").upper()
    model = ep.get("judge_model") or ""
    key = ""
    enc = getattr(space, "judge_api_key_enc", None)
    if enc:
        from app.services.providers_crypto import decrypt_key
        key = decrypt_key(enc)
    if not key:
        key = os.environ.get(_ENV_KEYS.get(fam, ""), "")
    if not key:
        raise RuntimeError(f"no {fam} key for the judge")
    return _build(fam, model, key, "", max_tokens), f"{fam}:{model}"


def _default_judge(db, space, max_tokens):
    """No judge configured → first company LLM provider ≠ the RAG's own."""
    from app.models.api_provider import ApiProvider
    from app.services.providers_crypto import decrypt_key
    from app.services.provider_models import models_for_family
    rag_provider_id = getattr(space, "llm_provider_id", None)
    for p in db.query(ApiProvider).all():
        kind = p.kind.value if hasattr(p.kind, "value") else str(p.kind)
        if kind != "LLM" or not p.api_key_encrypted or p.id == rag_provider_id:
            continue
        fam = p.family.value if hasattr(p.family, "value") else str(p.family)
        catalog = models_for_family(fam)
        if not catalog:
            continue
        model = catalog[0]["id"]
        return (_build(fam, model, decrypt_key(p.api_key_encrypted),
                       p.base_url or "", max_tokens),
                f"company:{p.name}:{model}")
    raise RuntimeError("no independent company LLM provider")


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
        out = json_from(_invoke_with_retry(judge, _CORRECTNESS_PROMPT.format(
            question=question,
            expected=expected or "(no ground truth — judge answer quality alone)",
            context=(context or "")[:5000], answer=(answer or "")[:2000],
        )))
        if not isinstance(out, dict):
            return None, None
        score = max(0.0, min(1.0, float(out.get("correctness"))))
        return round(score, 3), str(out.get("reason", ""))[:300]
    except Exception as e:
        logger.warning(f"[EVAL] correctness judge failed: {e}")
        return None, None
