"""
Query transforms — LLM-powered query rewriting, all OPTIONAL and fail-safe.

    rewrite_query : reformulate a vague/conversational query for retrieval
    hyde          : write a short hypothetical ANSWER and embed THAT
                    (HyDE — hypothetical document embeddings)
    multi_query   : generate 2-3 phrasing variants; they feed BM25 (as extra
                    query tokens) and fusion recall

They resolve the LLM through the platform's own llm_factory (the space's
provider/key). No key / any error → the original query is used untouched —
transforms can only ever ADD signal, never break retrieval.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _llm_complete(db, space, prompt: str, max_tokens: int = 220) -> str:
    """One short completion through the platform's LLM factory (the space's
    resolved provider/model/key). '' on any failure."""
    try:
        from app.services.llm_factory import get_llm
        from app.services.llm_factory.resolver import resolve_llm_config
        conf = resolve_llm_config(db, space)
        llm = get_llm(
            family=conf["family"], model=conf["model"],
            api_key=conf.get("api_key", ""), base_url=conf.get("base_url", ""),
            temperature=0.1, max_tokens=max_tokens,
        )
        resp = llm.invoke(prompt)
        return (getattr(resp, "content", None) or "").strip()
    except Exception as e:
        logger.warning(f"[RETRIEVAL/transform] LLM unavailable ({e}) — skipped")
        return ""


def apply_transforms(db, space, cfg, q) -> None:
    """Mutates the AnalyzedQuery in place. Only runs for semantic/keyword-ish
    intents — identifiers and filenames must stay literal."""
    if q.intent in ("exact_id", "filename", "metadata"):
        return
    if not (cfg.rewrite_query or cfg.hyde or cfg.multi_query):
        return

    # ── rewrite: better search phrasing for vague queries ──
    if cfg.rewrite_query:
        out = _llm_complete(
            db, space,
            "Rewrite this search query to be precise and self-contained for "
            "document retrieval. Reply with ONLY the rewritten query, same "
            f"language.\n\nQuery: {q.raw}",
        )
        if out and 3 <= len(out) <= 300:
            q.expansions.append(out)
            q.rewritten = out            # dense embeds the rewritten form too

    # ── HyDE: embed a hypothetical answer instead of the bare question ──
    if cfg.hyde:
        out = _llm_complete(
            db, space,
            "Write a short factual paragraph (3-4 sentences) that would "
            "plausibly answer this question, as it might appear inside an "
            f"internal company document. Same language. Question: {q.raw}",
        )
        if out and len(out) > 40:
            q.hyde_text = out            # orchestrator embeds this text

    # ── multi-query: phrasing variants widen recall ──
    if cfg.multi_query:
        out = _llm_complete(
            db, space,
            "Generate 3 alternative search queries for the question below — "
            "synonyms, related entities, more specific phrasings. One per "
            f"line, no numbering, same language.\n\nQuestion: {q.raw}",
        )
        for line in (out or "").splitlines():
            v = line.strip(" -•\t")
            if 3 <= len(v) <= 200 and v.lower() != q.raw.lower():
                q.expansions.append(v)
        q.expansions = list(dict.fromkeys(q.expansions))[:8]
