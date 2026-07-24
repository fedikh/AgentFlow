"""
Embedding Factory — mirror of the LLM factory, for embeddings.

Returns an embedder exposing the SAME interface as LangChain embeddings:
    .embed_documents(list[str]) -> list[list[float]]
    .embed_query(str)          -> list[float]

Families:
    LOCAL   → BGE-M3 via sentence-transformers (free, 1024 dims, the default)
    OPENAI  → OpenAIEmbeddings (text-embedding-3-*, forced to 1024 dims)
    VOYAGE  → VoyageAIEmbeddings (voyage-3.5*, natively 1024 dims)

The factory does NOT decide which key/model to use — that's resolver.py's job.

IMPORTANT (Batch 6): pgvector is fixed at 1024 dimensions. The models listed
in the embedding catalog all produce 1024-d vectors. Switching to a model with
a different dimension requires re-embedding every chunk — a proper RAGVersion
mechanism comes later. generate.py guards against dimension mismatch.
"""
import logging

logger = logging.getLogger(__name__)


class _LocalEmbedder:
    """BGE-M3 (1024-d) via sentence-transformers, cached process-wide."""
    _model = None

    def _get(self):
        if _LocalEmbedder._model is None:
            import os
            os.environ["TRANSFORMERS_NO_TF"] = "1"
            os.environ["USE_TF"] = "0"
            from sentence_transformers import SentenceTransformer
            try:
                logger.info("[EMB] Loading BGE-M3 (1024d)…")
                _LocalEmbedder._model = SentenceTransformer("BAAI/bge-m3")
            except Exception as e1:
                logger.warning(f"[EMB] BGE-M3 failed: {e1}")
                try:
                    _LocalEmbedder._model = SentenceTransformer("BAAI/bge-base-en-v1.5")
                except Exception:
                    _LocalEmbedder._model = SentenceTransformer("all-MiniLM-L6-v2")
        return _LocalEmbedder._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = self._get()
        vecs = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return [v.tolist() for v in vecs]

    def embed_query(self, text: str) -> list[float]:
        model = self._get()
        vec = model.encode(
            "Represent this sentence: " + text,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return vec.tolist()


def local_embedder() -> _LocalEmbedder:
    return _LocalEmbedder()


def _fit_1024(vec, dim: int = 1024):
    """Fit any embedding to the fixed pgvector width (1024): zero-pad if shorter,
    truncate if longer, then L2-normalize. Padding preserves cosine similarity
    between vectors from the SAME model, so retrieval stays consistent as long as
    indexing and querying use the same model (they do)."""
    import math
    v = [float(x) for x in (vec or [])]
    if len(v) < dim:
        v = v + [0.0] * (dim - len(v))
    elif len(v) > dim:
        v = v[:dim]
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class _FitTo1024:
    """Adapter that fits ANY LangChain-style embedder's output to the fixed
    1024-d pgvector column (pad/truncate + L2-normalize). Used for providers
    whose models don't natively emit 1024 dims (e.g. Gemini's 3072)."""

    def __init__(self, inner):
        self.inner = inner

    def embed_documents(self, texts):
        return [_fit_1024(v) for v in self.inner.embed_documents(texts)]

    def embed_query(self, text):
        return _fit_1024(self.inner.embed_query(text))


class _OllamaEmbedder:
    """Embeddings from a local Ollama daemon (mxbai-embed-large, nomic-embed-text,
    all-minilm, …). Vectors are fit to 1024 so any model works with the fixed
    pgvector column. No API key — Ollama runs locally."""

    def __init__(self, model: str = "", base_url: str = ""):
        import os
        self.model = model or "mxbai-embed-large"
        self.base = (base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")

    def _one(self, text: str):
        import requests
        r = requests.post(
            f"{self.base}/api/embeddings",
            json={"model": self.model, "prompt": text or ""},
            timeout=120,
        )
        r.raise_for_status()
        return _fit_1024(r.json().get("embedding") or [])

    def embed_documents(self, texts):
        return [self._one(t) for t in texts]

    def embed_query(self, text):
        return self._one(text)


def get_embedder(family: str, model: str = "", api_key: str = "", base_url: str = ""):
    """Build an embedder for the given family. Returns a LangChain-style object."""
    fam = (family or "LOCAL").upper()

    if fam == "OLLAMA":
        return _OllamaEmbedder(model=model, base_url=base_url)

    if fam == "LOCAL":
        return _LocalEmbedder()

    if fam == "OPENAI":
        from langchain_openai import OpenAIEmbeddings
        kwargs = dict(
            model=model or "text-embedding-3-small",
            api_key=api_key,
            dimensions=1024,   # force 1024 to match the pgvector column
        )
        if base_url:
            kwargs["base_url"] = base_url
        return OpenAIEmbeddings(**kwargs)

    if fam == "VOYAGE":
        from langchain_voyageai import VoyageAIEmbeddings
        return VoyageAIEmbeddings(
            model=model or "voyage-3.5",
            voyage_api_key=api_key,
        )

    if fam == "GOOGLE":
        # Gemini embeddings (gemini-embedding-*). Native dims differ from our
        # fixed pgvector width (e.g. 3072), so wrap with the 1024 fitter.
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        m = model or "gemini-embedding-001"
        if not m.startswith("models/"):
            m = f"models/{m}"
        return _FitTo1024(GoogleGenerativeAIEmbeddings(model=m, google_api_key=api_key))

    # Unknown family → safe local default
    logger.warning(f"[EMB] Unknown embedding family '{family}', using local BGE-M3")
    return _LocalEmbedder()
