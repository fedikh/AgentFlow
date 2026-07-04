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


def models_for_family(family: str) -> list:
    """Return the recommended models for a provider family (empty if unknown)."""
    return PROVIDER_MODELS.get((family or "").upper(), [])