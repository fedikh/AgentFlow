"""
Provider model catalog — the models the system knows for each family.

The Admin does NOT type model names. They only add: name + family + key.
The IT then picks a model from this catalog for the chosen family.

Keep this list current as providers release/retire models. These are the
model IDs sent to the provider's API (must match exactly).
"""

PROVIDER_MODELS = {
    "OPENAI": [
        {"id": "gpt-4o-mini",   "label": "GPT-4o mini"},
        {"id": "gpt-4o",        "label": "GPT-4o"},
        {"id": "gpt-4-turbo",   "label": "GPT-4 Turbo"},
        {"id": "gpt-4.1-mini",  "label": "GPT-4.1 mini"},
    ],
    "ANTHROPIC": [
        {"id": "claude-haiku-4-5",   "label": "Claude Haiku 4.5"},
        {"id": "claude-sonnet-4-5",  "label": "Claude Sonnet 4.5"},
    ],
    "GOOGLE": [
        {"id": "gemini-2.5-flash",       "label": "Gemini 2.5 Flash"},
        {"id": "gemini-2.5-flash-lite",  "label": "Gemini 2.5 Flash-Lite"},
        {"id": "gemini-2.0-flash",       "label": "Gemini 2.0 Flash"},
    ],
    "GROQ": [
        {"id": "llama-3.3-70b-versatile", "label": "Llama 3.3 70B"},
        {"id": "llama-3.1-8b-instant",    "label": "Llama 3.1 8B (fast)"},
    ],
    "OLLAMA": [
        {"id": "llama3",  "label": "Llama 3 (local)"},
        {"id": "mistral", "label": "Mistral (local)"},
        {"id": "phi3",    "label": "Phi-3 (local)"},
    ],
    "VOYAGE": [],   # embeddings only
    "LOCAL":  [],
    "CUSTOM": [],
}


def models_for_family(family: str) -> list:
    """Return the known models for a provider family (empty if unknown)."""
    return PROVIDER_MODELS.get((family or "").upper(), [])