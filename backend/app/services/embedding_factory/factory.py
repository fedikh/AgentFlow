"""
Embedding Factory — mirror of the LLM factory, for embeddings.

Returns an embedder exposing the SAME interface as LangChain embeddings:
    .embed_documents(list[str]) -> list[list[float]]
    .embed_query(str)          -> list[float]

Families:
    LOCAL   → sentence-transformers (BGE-M3 1024 ★ default, Jina v3 1024)
    OPENAI  → OpenAIEmbeddings (text-embedding-3-*, default 1536/3072 dims)
    VOYAGE  → VoyageAIEmbeddings (voyage-4* / voyage-3.5*, default 1024 dims)
    GOOGLE  → Gemini embeddings (default 3072 dims)
    OLLAMA  → local Ollama daemon (qwen3-embedding 1024/2560,
              nomic 768, embeddinggemma 768, minilm 384)

The factory does NOT decide which key/model to use — that's resolver.py's job.

DIMENSIONS: every model emits its NATIVE dimension. Vectors are stored in
per-dimension bucket tables (chunk_vectors_<dim>, see pgvector_store.py) and
the space records its dim (rag_spaces.embedding_dim). Switching to a model
with a different dimension flags the space for re-indexing — the config-drift
flow already enforces that.
"""
import logging

logger = logging.getLogger(__name__)


class _LocalEmbedder:
    """Local sentence-transformers models at their DEFAULT dimension, cached
    process-wide PER MODEL (dimension buckets store each dim natively):
        BAAI/bge-m3                 1024, multilingual ★ (default)
        jinaai/jina-embeddings-v3   1024, multilingual (trust_remote_code)
    """
    _models: dict = {}

    def __init__(self, model_name: str = ""):
        self.name = (model_name or "BAAI/bge-m3").strip()

    def _get(self):
        if self.name not in _LocalEmbedder._models:
            import os
            os.environ["TRANSFORMERS_NO_TF"] = "1"
            os.environ["USE_TF"] = "0"
            from sentence_transformers import SentenceTransformer
            kwargs = {}
            # jina-embeddings-v3 ships custom modeling code on the Hub
            if "jina-embeddings" in self.name.lower():
                kwargs["trust_remote_code"] = True
            try:
                logger.info(f"[EMB] Loading local model {self.name}…")
                _LocalEmbedder._models[self.name] = SentenceTransformer(self.name, **kwargs)
            except Exception as e1:
                logger.warning(f"[EMB] {self.name} failed ({e1}) — falling back to BGE-M3")
                _LocalEmbedder._models[self.name] = SentenceTransformer("BAAI/bge-m3")
        return _LocalEmbedder._models[self.name]

    def _query_prefix(self) -> str:
        # model-family specific query instruction (bge wants one, e5 wants
        # "query: ", plain sentence-transformers models want none)
        low = self.name.lower()
        if "bge" in low:
            return "Represent this sentence: "
        if "e5" in low:
            return "query: "
        return ""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = self._get()
        vecs = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return [v.tolist() for v in vecs]

    def embed_query(self, text: str) -> list[float]:
        model = self._get()
        vec = model.encode(
            self._query_prefix() + text,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return vec.tolist()


def local_embedder() -> _LocalEmbedder:
    return _LocalEmbedder()



class _OllamaEmbedder:
    """Embeddings from a local Ollama daemon (qwen3-embedding:*, nomic-embed-text,
    embeddinggemma:300m, all-minilm, …) at each model's DEFAULT dimension.
    No API key — local."""

    def __init__(self, model: str = "", base_url: str = ""):
        import os
        self.model = model or "nomic-embed-text"
        self.base = (base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")

    def _one(self, text: str):
        import requests
        r = requests.post(
            f"{self.base}/api/embeddings",
            json={"model": self.model, "prompt": text or ""},
            timeout=120,
        )
        r.raise_for_status()
        return [float(x) for x in (r.json().get("embedding") or [])]

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
        return _LocalEmbedder(model)   # honors the chosen local model + its native dim

    if fam == "OPENAI":
        from langchain_openai import OpenAIEmbeddings
        kwargs = dict(
            model=model or "text-embedding-3-small",
            api_key=api_key,
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
        # Gemini embeddings (gemini-embedding-*) at native dims (3072).
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        m = model or "gemini-embedding-001"
        if not m.startswith("models/"):
            m = f"models/{m}"
        return GoogleGenerativeAIEmbeddings(model=m, google_api_key=api_key)

    # Unknown family → safe local default
    logger.warning(f"[EMB] Unknown embedding family '{family}', using local BGE-M3")
    return _LocalEmbedder()
