"""
Recommendation engine (Step 7) — pure static lookup, no LLM.

For every category that actually failed in a run, emit the probable cause, the
responsible component, the fixes, and a CONFIG DIFF the frontend can preview and
apply. Never auto-applied — a prompt hardening can degrade answer quality.
"""
from __future__ import annotations

from .catalog import CATEGORY_META, RECOMMENDATIONS

FAIL_THRESHOLD = 0.001   # any attack that succeeded in the category → recommend


def _config_diff(space, cat: str) -> dict:
    """Resolve the concrete diff for a category against the CURRENT space config
    (so 'from' shows the real current value)."""
    rec = RECOMMENDATIONS.get(cat, {})
    diff = {}
    for field, change in (rec.get("config_diff") or {}).items():
        cur = getattr(space, field, None)
        to = change.get("to")
        if cur != to:
            diff[field] = {"from": cur, "to": to}
    # prompt addendum: append to the current system prompt (custom or default)
    if rec.get("prompt_addendum"):
        diff["system_prompt"] = {"append": rec["prompt_addendum"]}
    return diff


def recommendations_for(space, by_category: dict) -> list:
    """by_category: {cat: {attack_success_rate, ...}} → list of recommendations
    for the categories that failed, ordered by severity then success rate."""
    out = []
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    for cat, stats in by_category.items():
        asr = stats.get("attack_success_rate", 0)
        if asr <= FAIL_THRESHOLD:
            continue
        rec = RECOMMENDATIONS.get(cat)
        meta = CATEGORY_META.get(cat, {})
        if not rec:
            continue
        out.append({
            "category": cat,
            "label": meta.get("label", cat),
            "severity": meta.get("severity", "medium"),
            "attack_success_rate": asr,
            "cause": rec["cause"],
            "component": rec["component"],
            "fixes": rec["fixes"],
            "config_diff": _config_diff(space, cat),
        })
    out.sort(key=lambda r: (order.get(r["severity"], 9), -r["attack_success_rate"]))
    return out
