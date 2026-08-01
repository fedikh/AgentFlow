"""
Scoring — performance. Latency + token/cost estimates, pure Python.

Cost comes from litellm's maintained cost map (~3000 models, $/token for
input and output) — looked up by exact model id, then by common provider
prefixes, then by a tiny static fallback so local/unknown models estimate
as free instead of failing. Prices are ESTIMATES, not billing data.
"""
from __future__ import annotations

from ..common import logger

# static last-resort fallback ($ per 1M tokens: input, output)
_FALLBACK_PRICES = {
    "gpt-5": (10.0, 30.0), "gpt-4o-mini": (0.15, 0.60), "gpt-4o": (2.5, 10.0),
    "gpt-4.1-mini": (0.4, 1.6), "gpt-4.1": (2.0, 8.0),
    "claude-opus": (5.0, 25.0), "claude-sonnet": (3.0, 15.0), "claude-haiku": (1.0, 5.0),
    "gemini-2.5-pro": (1.25, 10.0), "gemini-2.5-flash": (0.30, 2.50),
}

_litellm_cost: dict | None = None


def _cost_map() -> dict:
    """litellm's model→cost map, loaded once (the import is heavy)."""
    global _litellm_cost
    if _litellm_cost is None:
        try:
            import litellm
            _litellm_cost = litellm.model_cost or {}
        except Exception as e:                 # pragma: no cover
            logger.warning(f"[EVAL] litellm unavailable ({e}) — static prices only")
            _litellm_cost = {}
    return _litellm_cost


def price_for(model: str) -> tuple[float, float]:
    """($ per 1M input tokens, $ per 1M output tokens) for a model id.
    litellm cost map first; static substring fallback; (0, 0) for local."""
    m = (model or "").strip()
    if not m:
        return (0.0, 0.0)
    cost = _cost_map()
    entry = None
    for key in (m, m.lower(), f"openai/{m}", f"anthropic/{m}", f"gemini/{m}",
                f"groq/{m}", f"vertex_ai/{m}"):
        if key in cost:
            entry = cost[key]
            break
    if entry:
        return (float(entry.get("input_cost_per_token") or 0) * 1e6,
                float(entry.get("output_cost_per_token") or 0) * 1e6)
    low = m.lower()
    for key, prices in _FALLBACK_PRICES.items():
        if key in low:
            return prices
    return (0.0, 0.0)          # local / unknown → free estimate


def case_cost(question: str, context: str, answer: str, model: str) -> dict:
    """Token + cost estimate for one case (chars/4 ≈ tokens)."""
    in_price, out_price = price_for(model)
    tok_in = (len(context or "") + len(question or "")) // 4
    tok_out = len(answer or "") // 4
    return {
        "est_tokens": tok_in + tok_out,
        "est_cost": round((tok_in * in_price + tok_out * out_price) / 1e6, 6),
    }
