"""
OpenAI access for LLM-based and agentic chunking.

Two public pieces:
  * resolve_openai(db, space) → {api_key, model, base_url} | None
        Where the OpenAI key comes from, in priority order:
          1. the space's OWN LLM key when its provider is OPENAI (decrypted),
          2. a company OPENAI provider attached to the space,
          3. settings.OPENAI_API_KEY,
          4. settings.VISION_API_KEY (it's an OpenAI key when VISION_PROVIDER=openai).
        Returns None when no key is available → callers fall back to structural
        chunking so indexing never breaks.
  * llm_json / make_llm_split — thin, defensive wrappers over langchain ChatOpenAI.

Everything here is best-effort: a network/quota/parse failure returns None (or a
non-LLM fallback), it never raises into the chunking pipeline.
"""
import json
import logging

logger = logging.getLogger(__name__)

# OpenAI model prefixes we're willing to keep from a space's llm_model.
_OPENAI_PREFIXES = ("gpt-", "o1", "o3", "o4", "chatgpt")


def _openai_model(candidate: str) -> str:
    from app.config import settings
    c = (candidate or "").strip().lower()
    if c and any(c.startswith(p) for p in _OPENAI_PREFIXES):
        return candidate
    return getattr(settings, "CHUNK_LLM_MODEL", "") or "gpt-4o-mini"


def resolve_openai(db, space) -> dict | None:
    """Resolve an OpenAI access config for chunking, or None."""
    from app.config import settings

    # 1. space's own key (only when its provider family is OPENAI)
    try:
        fam = (getattr(space, "llm_provider", "") or "").upper()
        enc = getattr(space, "llm_api_key_enc", None)
        if fam == "OPENAI" and enc:
            from app.services.providers_crypto import decrypt_key
            key = decrypt_key(enc)
            if key:
                return {"api_key": key,
                        "model": _openai_model(getattr(space, "llm_model", "")),
                        "base_url": getattr(space, "llm_base_url", "") or ""}
    except Exception as e:
        logger.warning(f"[CHUNK-LLM] own-key resolve failed: {e}")

    # 2. company provider attached to the space (family OPENAI)
    try:
        pid = getattr(space, "llm_provider_id", None)
        if pid and db is not None:
            from app.models.api_provider import ApiProvider
            p = db.query(ApiProvider).filter(ApiProvider.id == pid).first()
            pfam = (getattr(p, "family", None)
                    and (p.family.value if hasattr(p.family, "value") else str(p.family)) or "")
            if p and "OPENAI" in pfam.upper() and getattr(p, "api_key_encrypted", None):
                from app.services.providers_crypto import decrypt_key
                key = decrypt_key(p.api_key_encrypted)
                if key:
                    return {"api_key": key,
                            "model": _openai_model(getattr(space, "llm_model", "")),
                            "base_url": getattr(p, "base_url", "") or ""}
    except Exception as e:
        logger.warning(f"[CHUNK-LLM] provider resolve failed: {e}")

    # 3. explicit OPENAI_API_KEY
    if getattr(settings, "OPENAI_API_KEY", ""):
        return {"api_key": settings.OPENAI_API_KEY,
                "model": getattr(settings, "CHUNK_LLM_MODEL", "") or "gpt-4o-mini",
                "base_url": ""}

    # 4. reuse the vision key when it's an OpenAI key
    if (getattr(settings, "VISION_PROVIDER", "openai") or "").lower() == "openai" \
            and getattr(settings, "VISION_API_KEY", ""):
        return {"api_key": settings.VISION_API_KEY,
                "model": getattr(settings, "CHUNK_LLM_MODEL", "") or "gpt-4o-mini",
                "base_url": ""}

    return None


# ── ChatOpenAI wrapper (cached per key/model) ──
_CLIENTS: dict = {}


def _client(access: dict, temperature: float = 0.1):
    key = (access.get("api_key"), access.get("model"), access.get("base_url"), temperature)
    if key not in _CLIENTS:
        from langchain_openai import ChatOpenAI
        kwargs = dict(model=access.get("model") or "gpt-4o-mini",
                      api_key=access["api_key"], temperature=temperature,
                      max_retries=1, timeout=45)
        if access.get("base_url"):
            kwargs["base_url"] = access["base_url"]
        _CLIENTS[key] = ChatOpenAI(**kwargs)
    return _CLIENTS[key]


def llm_json(access: dict, system: str, user: str, temperature: float = 0.1) -> dict | None:
    """Call OpenAI expecting a JSON object; return the parsed dict or None."""
    if not access or not access.get("api_key"):
        return None
    try:
        llm = _client(access, temperature).bind(
            response_format={"type": "json_object"})
        resp = llm.invoke([("system", system), ("human", user)])
        content = resp.content if hasattr(resp, "content") else str(resp)
        if isinstance(content, list):  # some providers return content parts
            content = "".join(p.get("text", "") if isinstance(p, dict) else str(p)
                              for p in content)
        return json.loads(content)
    except Exception as e:
        logger.warning(f"[CHUNK-LLM] json call failed: {e}")
        return None


# ── LLM-backed text splitter (shared by the "llm" strategy and the agentic
#    Semantic Boundary Detector) ──

# Text longer than this is pre-split structurally before the LLM sees it, to
# bound cost/latency and avoid truncated completions.
_MAX_LLM_TEXT = 9000


def make_llm_split(access: dict, max_chars: int = 1200):
    """Return split_fn(text) → [passages] that asks OpenAI to divide text into
    coherent, self-contained passages of roughly max_chars, preserving the
    original wording. Falls back to sentence-aware recursive splitting when
    there's no key, the text is short/huge, or the model misbehaves (validated
    by a length-conservation check so content is never dropped or rewritten)."""
    from .base import split_recursive

    def _fallback(text: str) -> list:
        return split_recursive(text, max_chars, max(48, max_chars // 10))

    if not access or not access.get("api_key"):
        return _fallback

    sys = (
        "You are a document chunking engine for a retrieval system. Split the "
        "user's text into coherent, self-contained passages for embedding. "
        f"Each passage should be roughly {max_chars} characters, and MUST break "
        "only at natural boundaries (paragraph or sentence ends) — never mid-"
        "sentence. Keep each passage focused on a single topic or idea. "
        "CRITICAL: reproduce the ORIGINAL text verbatim, only divided — do not "
        "summarize, rewrite, translate, add, or remove any words. Return JSON: "
        '{"passages": ["...", "..."]}.'
    )

    def _split(text: str) -> list:
        if not text or not text.strip():
            return []
        # short → one passage; huge → structural pre-split, LLM per window
        if len(text) <= int(max_chars * 1.3):
            return [text.strip()]
        if len(text) > _MAX_LLM_TEXT:
            out = []
            for window in split_recursive(text, _MAX_LLM_TEXT, 0):
                out.extend(_split_one(window))
            return out or _fallback(text)
        return _split_one(text)

    def _split_one(text: str) -> list:
        data = llm_json(access, sys, text)
        passages = (data or {}).get("passages")
        if not isinstance(passages, list) or not passages:
            return _fallback(text)
        passages = [str(p).strip() for p in passages if str(p).strip()]
        if not passages:
            return _fallback(text)
        # length-conservation guard: reject paraphrase/truncation (content safety)
        total = sum(len(p) for p in passages)
        if not (0.85 * len(text) <= total <= 1.20 * len(text)):
            logger.info("[CHUNK-LLM] passage length drift (%d vs %d) → fallback",
                        total, len(text))
            return _fallback(text)
        return passages

    return _split
