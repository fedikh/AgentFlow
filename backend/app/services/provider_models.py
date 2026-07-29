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
        # GPT-4 family (widely used, stable)
        {"id": "gpt-4.1",       "label": "GPT-4.1"},
        {"id": "gpt-4.1-mini",  "label": "GPT-4.1 mini"},
        {"id": "gpt-4o",        "label": "GPT-4o"},
        {"id": "gpt-4o-mini",   "label": "GPT-4o mini"},
        {"id": "gpt-4-turbo",   "label": "GPT-4 Turbo (legacy)"},
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
        {"id": "gemini-3.1-pro",         "label": "Gemini 3.1 Pro (flagship)"},
    ],
    "GROQ": [
        {"id": "llama-3.3-70b-versatile", "label": "Llama 3.3 70B (default)"},
        {"id": "llama-3.1-8b-instant",    "label": "Llama 3.1 8B (fastest)"},
    ],
    # OLLAMA models are listed LIVE from the local daemon (/api/tags); this
    # static list is only a documentation/fallback hint.
    "OLLAMA": [
        {"id": "llama3.1:8b",  "label": "Llama 3.1 8B (local)"},
        {"id": "llama3.2:3b",  "label": "Llama 3.2 3B (local, fast)"},
        {"id": "gemma3:4b",    "label": "Gemma 3 4B (local)"},
        {"id": "mistral",      "label": "Mistral (local)"},
        {"id": "phi3",         "label": "Phi-3 (local)"},
    ],
    "CUSTOM": [],
}


# ══════════════════════════════════════════════════════
# EMBEDDING model catalog (Batch 6)
# Every model is listed at its DEFAULT output dimension (what the API/library
# returns when no `dimensions`/`output_dimension` param is sent). Vectors are
# stored natively in per-dimension bucket tables (see pgvector_store.py).
# Switching to a model whose dimension differs requires re-embedding
# (flagged in the UI).
# ══════════════════════════════════════════════════════

EMBEDDING_PROVIDER_MODELS = {
    "OPENAI": [
        {"id": "text-embedding-3-small", "label": "text-embedding-3-small (1536)", "dim": 1536},
        {"id": "text-embedding-3-large", "label": "text-embedding-3-large (3072)", "dim": 3072},
    ],
    # Voyage models default to 1024 output dims (voyage-4 / -3.5 / context
    # families are Matryoshka: 256/512/1024/2048 — we use the 1024 default).
    "VOYAGE": [
        {"id": "voyage-4-large",        "label": "voyage-4-large (1024)",        "dim": 1024},
        {"id": "voyage-4",              "label": "voyage-4 (1024)",              "dim": 1024},
        {"id": "voyage-4-lite",         "label": "voyage-4-lite (1024)",         "dim": 1024},
        {"id": "voyage-4-nano",         "label": "voyage-4-nano (1024)",         "dim": 1024},
        {"id": "voyage-context-4",      "label": "voyage-context-4 (1024, contextual)", "dim": 1024},
        {"id": "voyage-3.5",            "label": "voyage-3.5 (1024)",            "dim": 1024},
        {"id": "voyage-3.5-lite",       "label": "voyage-3.5-lite (1024)",       "dim": 1024},
        {"id": "voyage-3-large",        "label": "voyage-3-large (1024)",        "dim": 1024},
        {"id": "voyage-multimodal-3.5", "label": "Voyage Multimodal 3.5 (1024)", "dim": 1024},
        {"id": "voyage-code-3",         "label": "voyage-code-3 (1024, code)",   "dim": 1024},
        {"id": "voyage-finance-2",      "label": "voyage-finance-2 (1024, finance)", "dim": 1024},
        {"id": "voyage-law-2",          "label": "voyage-law-2 (1024, legal)",   "dim": 1024},
    ],
    # Gemini embeddings default to 3072 output dims (Matryoshka: 768/1536/3072
    # — we use the 3072 default; stored as halfvec, still HNSW-indexable).
    "GOOGLE": [
        {"id": "gemini-embedding-002", "label": "Gemini Embedding 2 (3072)", "dim": 3072},
        {"id": "gemini-embedding-001", "label": "Gemini Embedding 1 (3072)", "dim": 3072},
    ],
    # In-process sentence-transformers models, at their default dims.
    "LOCAL": [
        {"id": "BAAI/bge-m3", "label": "BGE-M3 (1024, multilingual) ★", "dim": 1024},
        {"id": "jinaai/jina-embeddings-v3", "label": "Jina Embeddings v3 (1024, multilingual)", "dim": 1024},
    ],
    # Ollama runs locally (no key). Each model at its default dimension.
    "OLLAMA": [
        {"id": "qwen3-embedding:0.6b", "label": "Qwen3-Embedding 0.6B (1024, local)", "dim": 1024},
        {"id": "qwen3-embedding:4b",   "label": "Qwen3-Embedding 4B (2560, local)",   "dim": 2560},
        {"id": "nomic-embed-text",     "label": "Nomic-Embed-Text (768, CPU-friendly)", "dim": 768},
        {"id": "embeddinggemma:300m",  "label": "EmbeddingGemma 300M (768, CPU-friendly)", "dim": 768},
        {"id": "all-minilm",           "label": "all-minilm (384, fastest)",       "dim": 384},
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


def capabilities_for_family(family: str) -> list:
    """
    Which provider kinds a family can serve, based on the catalogs above.
    A family that has BOTH chat and embedding models (e.g. OPENAI) is
    dual-capable: one admin key works for LLM *and* embeddings.

      OPENAI  → ["LLM", "EMBEDDING"]
      VOYAGE  → ["EMBEDDING"]
      GROQ / ANTHROPIC / GOOGLE / CUSTOM → ["LLM"]
    """
    fam = (family or "").upper()
    caps = []
    if fam in PROVIDER_MODELS:
        caps.append("LLM")
    if fam in EMBEDDING_PROVIDER_MODELS:
        caps.append("EMBEDDING")
    return caps