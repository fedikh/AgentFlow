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


def get_embedder(family: str, model: str = "", api_key: str = "", base_url: str = ""):
    """Build an embedder for the given family. Returns a LangChain-style object."""
    fam = (family or "LOCAL").upper()

    if fam in ("LOCAL", "OLLAMA"):
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

    # Unknown family → safe local default
    logger.warning(f"[EMB] Unknown embedding family '{family}', using local BGE-M3")
    return _LocalEmbedder()
