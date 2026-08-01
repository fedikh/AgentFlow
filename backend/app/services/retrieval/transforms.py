"""
Query Transformation — one LLM call that does all five jobs at once:

    · Query Rewrite       — precise, self-contained search phrasing
    · Query Expansion     — synonyms folded into the rewrite
    · Multi-Query         — up to 2 alternative phrasings (widen recall)
    · Spell Correction    — typos fixed
    · Noise Removal       — "please", "can you tell me…" stripped

Enabled by default (cfg.transform_enabled). Uses the SAME LLM as the space
(resolved through llm_factory). Identifiers, codes, numbers and filenames are
explicitly preserved by the prompt. Any failure → the original query is used
untouched — transformation can only ever ADD signal, never break retrieval.
"""
from __future__ import annotations

import json
import logging

from .types import Query

logger = logging.getLogger(__name__)

_PROMPT = """You improve search queries for a document-retrieval system.

Rules:
- Fix spelling, remove filler words, rewrite precisely and self-contained.
- NEVER change identifiers, codes, reference numbers or filenames
  (e.g. EMP2300114, INV-2026-001, rapport.pdf) — copy them exactly.
- Keep the same language as the input.

Reply with ONLY this JSON (no markdown):
{{"cleaned": "<improved query>", "variants": ["<alt phrasing 1>", "<alt phrasing 2>"]}}

Query: {query}"""


def enhance_query(db, space, q: Query) -> None:
    """Mutates q in place (cleaned / variants). Silent no-op on any failure."""
    try:
        from app.services.llm_factory import get_llm
        from app.services.llm_factory.resolver import resolve_llm_config
        conf = resolve_llm_config(db, space)
        llm = get_llm(
            family=conf["family"], model=conf["model"],
            api_key=conf.get("api_key", ""), base_url=conf.get("base_url", ""),
            temperature=0.1, max_tokens=200,
        )
        out = (getattr(llm.invoke(_PROMPT.format(query=q.raw)), "content", "") or "").strip()
        data = json.loads(out[out.find("{"): out.rfind("}") + 1])
        cleaned = str(data.get("cleaned") or "").strip()
        if 3 <= len(cleaned) <= 300:
            q.cleaned = cleaned
        q.variants = [str(v).strip() for v in (data.get("variants") or [])
                      if 3 <= len(str(v).strip()) <= 300][:2]
    except Exception as e:
        logger.warning(f"[RETRIEVAL/transform] skipped ({e}) — original query kept")
