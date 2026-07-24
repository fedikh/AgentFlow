"""
Evaluation — shared constants and small helpers used by every module.
"""
from __future__ import annotations

import json
import logging
import os
import re

logger = logging.getLogger("app.services.evaluation")

# Silence Hugging Face hub noise triggered by ragas/datasets imports.
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

CATEGORIES = [
    "semantic", "exact_id", "entity_lookup", "table", "structured_data",
    "aggregation", "multi_doc", "multi_hop", "summarization", "reasoning",
    "multilingual",
]

# Plain-language question types shown to domain experts (label → slug)
PLAIN_TYPES = [
    ("Find information (general)", "semantic"),
    ("Look up a code / ID / reference", "exact_id"),
    ("Find a person / company / name", "entity_lookup"),
    ("Question about a table", "table"),
    ("Question about CSV / Excel data", "structured_data"),
    ("Counting / totals (how many…)", "aggregation"),
    ("Needs several documents", "multi_doc"),
    ("Needs several facts combined", "multi_hop"),
    ("Summary question", "summarization"),
    ("Reasoning / why question", "reasoning"),
    ("Different language than the document", "multilingual"),
]
TYPE_BY_LABEL = {label.lower(): slug for label, slug in PLAIN_TYPES}

# Rough $/1M tokens (input, output) for COST ESTIMATES (not billing data).
_PRICES = {
    "gpt-5": (10.0, 30.0), "gpt-4o-mini": (0.15, 0.60), "gpt-4o": (2.5, 10.0),
    "gpt-4.1-mini": (0.4, 1.6), "gpt-4.1": (2.0, 8.0),
    "claude-opus": (5.0, 25.0), "claude-sonnet": (3.0, 15.0), "claude-haiku": (1.0, 5.0),
    "gemini-2.5-pro": (1.25, 10.0), "gemini-2.5-flash": (0.30, 2.50),
    "gemini-3": (2.0, 12.0),
}


def price_for(model: str):
    m = (model or "").lower()
    for k, v in _PRICES.items():
        if k in m:
            return v
    return (0.0, 0.0)          # local / groq / unknown → free estimate


def json_from(text: str):
    """Best-effort JSON object/array extraction from an LLM reply."""
    m = re.search(r"[\[{].*[\]}]", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def strip_accents(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def eval_params(space) -> dict:
    try:
        d = json.loads(getattr(space, "eval_params", None) or "{}")
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


# ── OpenAI reasoning models (gpt-5, o1, o3, o4…) reject any temperature
#    other than the default 1 — even Ragas's internal 0.01 override. ──
_REASONING_RE = re.compile(r"^(o[134](-|$)|gpt-5(-|$)|gpt-5$)")


def is_reasoning_model(model: str) -> bool:
    return bool(_REASONING_RE.match((model or "").strip().lower()))


_PAYLOAD_PATCHED = False


def _patch_openai_payload():
    """Strip 'temperature' from every OpenAI request whose model is a
    reasoning model (gpt-5 / o1 / o3 / o4…). This is the only reliable layer:
    Ragas MUTATES the shared client's temperature attribute at generate time
    (to 0.01), so pinning the attribute or using disabled_params is not
    enough — the payload itself must be cleaned."""
    global _PAYLOAD_PATCHED
    if _PAYLOAD_PATCHED:
        return
    try:
        from langchain_openai.chat_models.base import BaseChatOpenAI
        orig = BaseChatOpenAI._get_request_payload

        def patched(self, input_, *, stop=None, **kwargs):
            payload = orig(self, input_, stop=stop, **kwargs)
            if is_reasoning_model(str(payload.get("model", ""))):
                payload.pop("temperature", None)
            return payload

        BaseChatOpenAI._get_request_payload = patched
        _PAYLOAD_PATCHED = True
    except Exception as e:
        logger.warning(f"[EVAL] could not patch OpenAI payload: {e}")


def fix_reasoning_llm(llm, family: str, model: str):
    """Make an OpenAI reasoning-model client safe for evaluation frameworks."""
    if (family or "").upper() != "OPENAI" or not is_reasoning_model(model):
        return llm
    _patch_openai_payload()
    try:
        llm.temperature = 1
    except Exception as e:
        logger.warning(f"[EVAL] could not pin reasoning-model params: {e}")
    return llm


def space_llm(db, space, max_tokens=900):
    """The space's own LLM (chat model), temperature 0 for determinism."""
    from app.services.llm_factory import get_llm
    from app.services.llm_factory.resolver import resolve_llm_config
    conf = resolve_llm_config(db, space)
    llm = get_llm(family=conf["family"], model=conf["model"],
                  api_key=conf.get("api_key", ""), base_url=conf.get("base_url", ""),
                  temperature=0.0, max_tokens=max_tokens)
    return fix_reasoning_llm(llm, conf["family"], conf["model"])


def docs_of(db, space) -> list:
    from sqlalchemy import text as T
    return [r[0] for r in db.execute(
        T("SELECT file_name FROM documents WHERE rag_space_id=:s ORDER BY file_name LIMIT 80"),
        {"s": space.id}).fetchall()]
