"""
Provider model catalog — recommended chat models per family (fixed list).

The admin adds only name + family + key. The IT picks a model from this
curated list for the chosen family. No live API call — reliable and fast.

Models current as of mid-2026. To add/remove a model, edit this file only.
Only chat/generation models are listed (no embeddings/vision/audio).
"""

PROVIDER_MODELS = {
    "OPENAI": [
        {"id": "gpt-5.4-mini",  "label": "GPT-5.4 mini (fast, cheap)"},
        {"id": "gpt-5.4",       "label": "GPT-5.4"},
        {"id": "gpt-5.4-nano",  "label": "GPT-5.4 nano (cheapest)"},
        {"id": "gpt-5.5",       "label": "GPT-5.5 (flagship)"},
        {"id": "gpt-4o-mini",   "label": "GPT-4o mini (legacy)"},
        {"id": "gpt-4o",        "label": "GPT-4o (legacy)"},
    ],
    "ANTHROPIC": [
        {"id": "claude-haiku-4-5",   "label": "Claude Haiku 4.5 (fast, cheap)"},
        {"id": "claude-sonnet-4-6",  "label": "Claude Sonnet 4.6 (balanced)"},
        {"id": "claude-opus-4-8",    "label": "Claude Opus 4.8 (flagship)"},
    ],
    "GOOGLE": [
        {"id": "gemini-2.5-flash-lite",  "label": "Gemini 2.5 Flash-Lite (cheapest)"},
        {"id": "gemini-2.5-flash",       "label": "Gemini 2.5 Flash (best value)"},
        {"id": "gemini-2.5-pro",         "label": "Gemini 2.5 Pro"},
        {"id": "gemini-3.5-flash",       "label": "Gemini 3.5 Flash"},
        {"id": "gemini-3.1-flash-lite",  "label": "Gemini 3.1 Flash-Lite"},
        {"id": "gemini-3.1-pro",         "label": "Gemini 3.1 Pro (flagship)"},
    ],
    "GROQ": [
        {"id": "llama-3.3-70b-versatile", "label": "Llama 3.3 70B (default)"},
        {"id": "llama-3.1-8b-instant",    "label": "Llama 3.1 8B (fastest)"},
    ],
    "OLLAMA": [
        {"id": "llama3",  "label": "Llama 3 (local)"},
        {"id": "mistral", "label": "Mistral (local)"},
        {"id": "phi3",    "label": "Phi-3 (local)"},
    ],
    "CUSTOM": [],
}


# ══════════════════════════════════════════════════════
# EMBEDDING model catalog (Batch 6)
# pgvector is fixed at 1024 dims. Models that don't natively output 1024 are
# labelled; OpenAI text-embedding-3-* support a `dimensions` param to force
# 1024, and Voyage voyage-3(.5) are natively 1024. Switching to a model whose
# stored dimension differs requires re-embedding (flagged in the UI).
# ══════════════════════════════════════════════════════

EMBEDDING_PROVIDER_MODELS = {
    "OPENAI": [
        {"id": "text-embedding-3-small", "label": "text-embedding-3-small (1024)", "dim": 1024},
        {"id": "text-embedding-3-large", "label": "text-embedding-3-large (1024)", "dim": 1024},
    ],
    "VOYAGE": [
        {"id": "voyage-3.5",       "label": "voyage-3.5 (1024)",       "dim": 1024},
        {"id": "voyage-3.5-lite",  "label": "voyage-3.5-lite (1024)",  "dim": 1024},
        {"id": "voyage-3-large",   "label": "voyage-3-large (1024)",   "dim": 1024},
    ],
    "LOCAL": [
        {"id": "BAAI/bge-m3", "label": "BGE-M3 (1024, local)", "dim": 1024},
    ],
}


def models_for_family(family: str, kind: str = "LLM") -> list:
    """
    Return the recommended models for a provider family.
      kind="LLM"        → chat models (PROVIDER_MODELS)
      kind="EMBEDDING"  → embedding models (EMBEDDING_PROVIDER_MODELS)
    Empty list if unknown.
    """
    fam = (family or "").upper()
    if (kind or "LLM").upper() == "EMBEDDING":
        return EMBEDDING_PROVIDER_MODELS.get(fam, [])
    return PROVIDER_MODELS.get(fam, [])


def embedding_models_for_family(family: str) -> list:
    """Recommended EMBEDDING models for a family."""
    return EMBEDDING_PROVIDER_MODELS.get((family or "").upper(), [])