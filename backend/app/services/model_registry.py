"""
Model Registry — liste les modèles disponibles pour l'interface IT.

DEUX SOURCES :
  • LLMs       → récupérés EN DIRECT depuis l'API du provider (Groq, Ollama).
                 OpenAI est prêt mais désactivé (pas de clé pour l'instant).
  • Embeddings → registry CURATÉ en dur, car on a besoin de la DIMENSION de
                 chaque modèle (la colonne pgvector dépend de la dimension).

Pourquoi en direct pour les LLMs : la liste change souvent côté provider.
Pourquoi curaté pour les embeddings : l'API ne donne pas la dimension, et il
nous la faut pour valider la compatibilité avec la colonne Vector.

Tout est GRATUIT/LOCAL pour l'instant. Les modèles payants (OpenAI) sont dans
le registry avec available=False — on les activera quand la clé sera achetée.
"""
import os
import logging
import requests

logger = logging.getLogger(__name__)

# Cache simple en mémoire (évite d'appeler les APIs à chaque chargement de page)
_cache = {}
_CACHE_TTL = 300  # 5 minutes


# ══════════════════════════════════════════════════════
# EMBEDDINGS — registry curaté (dimension obligatoire)
# ══════════════════════════════════════════════════════

EMBEDDING_MODELS = [
    {
        "id": "BAAI/bge-m3",
        "provider": "LOCAL",
        "dim": 1024,
        "label": "BGE-M3",
        "note": "Local · gratuit · qualité élevée",
        "speed": 1,          # 1 = lent (CPU), 3 = rapide
        "available": True,
    },
    {
        "id": "BAAI/bge-base-en-v1.5",
        "provider": "LOCAL",
        "dim": 768,
        "label": "BGE-Base",
        "note": "Local · gratuit · équilibré",
        "speed": 2,
        "available": True,
    },
    {
        "id": "all-MiniLM-L6-v2",
        "provider": "LOCAL",
        "dim": 384,
        "label": "MiniLM",
        "note": "Local · gratuit · rapide",
        "speed": 3,
        "available": True,
    },
    # ── Ollama (local daemon, no key) — fit to 1024 to match pgvector ──
    {
        "id": "mxbai-embed-large",
        "provider": "OLLAMA",
        "dim": 1024,
        "label": "mxbai-embed-large",
        "note": "Ollama · local · 1024d (native match)",
        "speed": 2,
        "available": True,
    },
    {
        "id": "nomic-embed-text",
        "provider": "OLLAMA",
        "dim": 768,
        "label": "nomic-embed-text",
        "note": "Ollama · local · 768d → fit 1024",
        "speed": 3,
        "available": True,
    },
    {
        "id": "all-minilm",
        "provider": "OLLAMA",
        "dim": 384,
        "label": "all-minilm",
        "note": "Ollama · local · 384d → fit 1024",
        "speed": 3,
        "available": True,
    },
    # ── Payant — prêt mais désactivé (pas de clé) ──
    {
        "id": "text-embedding-3-small",
        "provider": "OPENAI",
        "dim": 1536,
        "label": "OpenAI Small",
        "note": "API · payant · rapide",
        "speed": 3,
        "available": False,
    },
    {
        "id": "text-embedding-3-large",
        "provider": "OPENAI",
        "dim": 3072,
        "label": "OpenAI Large",
        "note": "API · payant · qualité max",
        "speed": 3,
        "available": False,
    },
]


def list_embedding_models() -> list:
    """Retourne tous les modèles d'embedding (disponibles en premier)."""
    return sorted(EMBEDDING_MODELS, key=lambda m: (not m["available"], m["dim"]))


# ══════════════════════════════════════════════════════
# LLMs — récupérés en direct par provider
# ══════════════════════════════════════════════════════

def list_llm_models(provider: str) -> dict:
    """
    Retourne {provider, available, models:[{id,label}]} pour un provider donné.
    Gère les erreurs proprement : si l'API est down, available=False.
    """
    provider = (provider or "GROQ").upper()

    if provider == "GROQ":
        return _list_groq()
    if provider == "OLLAMA":
        return _list_ollama()
    if provider == "OPENAI":
        return _list_openai()

    return {"provider": provider, "available": False, "models": [], "error": "Provider inconnu"}


def _cached(key, fn):
    import time
    now = time.time()
    if key in _cache and now - _cache[key][0] < _CACHE_TTL:
        return _cache[key][1]
    result = fn()
    # On ne cache que les succès
    if result.get("available"):
        _cache[key] = (now, result)
    return result


def _list_groq() -> dict:
    def fetch():
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            return {"provider": "GROQ", "available": False, "models": [],
                    "error": "GROQ_API_KEY manquante"}
        try:
            r = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=8,
            )
            r.raise_for_status()
            data = r.json().get("data", [])
            # On garde les modèles de chat, on exclut whisper/audio
            models = [
                {"id": m["id"], "label": m["id"]}
                for m in data
                if "whisper" not in m["id"].lower()
                and "guard" not in m["id"].lower()
            ]
            models.sort(key=lambda m: m["id"])
            return {"provider": "GROQ", "available": True, "models": models}
        except Exception as e:
            logger.warning(f"[REGISTRY] Groq fetch failed: {e}")
            # Fallback : modèles connus pour ne pas bloquer l'UI
            return {
                "provider": "GROQ", "available": True,
                "models": [
                    {"id": "llama-3.3-70b-versatile", "label": "llama-3.3-70b-versatile"},
                    {"id": "llama-3.1-8b-instant", "label": "llama-3.1-8b-instant"},
                ],
                "error": f"API injoignable, liste de secours ({e})",
            }
    return _cached("groq", fetch)


def _list_ollama() -> dict:
    def fetch():
        base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        try:
            r = requests.get(f"{base}/api/tags", timeout=5)
            r.raise_for_status()
            data = r.json().get("models", [])
            models = [{"id": m["name"], "label": m["name"]} for m in data]
            return {"provider": "OLLAMA", "available": True, "models": models}
        except Exception as e:
            logger.warning(f"[REGISTRY] Ollama fetch failed: {e}")
            return {"provider": "OLLAMA", "available": False, "models": [],
                    "error": "Ollama non démarré (lance `ollama serve`)"}
    return _cached("ollama", fetch)


def _list_openai() -> dict:
    """Prêt mais désactivé tant qu'il n'y a pas de clé."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"provider": "OPENAI", "available": False, "models": [],
                "error": "Clé OpenAI non configurée (payant)"}
    try:
        r = requests.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=8,
        )
        r.raise_for_status()
        data = r.json().get("data", [])
        models = [
            {"id": m["id"], "label": m["id"]}
            for m in data
            if m["id"].startswith("gpt-")
        ]
        models.sort(key=lambda m: m["id"])
        return {"provider": "OPENAI", "available": True, "models": models}
    except Exception as e:
        return {"provider": "OPENAI", "available": False, "models": [], "error": str(e)}


# ══════════════════════════════════════════════════════
# Vue d'ensemble — tout en un appel
# ══════════════════════════════════════════════════════

def list_all_providers() -> dict:
    """Retourne l'état de tous les providers LLM + les embeddings, pour l'UI."""
    return {
        "llm_providers": {
            "GROQ": _list_groq(),
            "OLLAMA": _list_ollama(),
            "OPENAI": _list_openai(),
        },
        "embedding_models": list_embedding_models(),
    }