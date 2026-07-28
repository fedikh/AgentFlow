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
#    Boundary Agent) — BOUNDARY-PREDICTION design, the production approach ──
#
#  The LLM NEVER touches the text. The engine:
#    1. splits the section into numbered paragraphs,
#    2. asks the LLM which paragraph ids belong together ({"chunks": [[0,1],[2]]})
#       — it only sees short previews, never rewrites anything,
#    3. VALIDATES by paragraph ids (the groups must be a perfect consecutive
#       partition of 0..n-1 — far stronger than length heuristics),
#    4. rebuilds each chunk from the ORIGINAL paragraphs (verbatim by
#       construction — an LLM cannot alter text it never returns),
#    5. adds overlap itself (the engine, never the model).
#
#  Cost guards: sections under _NO_LLM_UNDER chars never call GPT (recursive
#  handles them); paragraph previews are capped; oversized sections are
#  windowed under _MAX_LLM_TEXT so no call can blow the context window.

_MAX_LLM_TEXT = 9000       # max chars of paragraphs handled per LLM call
_NO_LLM_UNDER = 1000       # sections smaller than this skip GPT entirely
_PREVIEW = 280             # chars of each paragraph shown to the model


def make_llm_split(access: dict, max_chars: int = 1200, overlap: int = 0):
    """Return split_fn(text) → [chunks] using boundary prediction (see above).
    Falls back to sentence-aware recursive splitting when there is no key,
    the section is small, or the model's grouping fails id validation."""
    from .base import split_recursive

    def _fallback(text: str) -> list:
        return split_recursive(text, max_chars, max(48, max_chars // 10))

    def _paragraphs(text: str) -> list:
        paras = [p.strip() for p in text.split("\n\n") if p.strip()]
        out = []
        for p in paras:
            if len(p) > max_chars * 2:            # giant paragraph → sentence pre-split
                out.extend(split_recursive(p, max_chars, 0))
            else:
                out.append(p)
        return out

    sys = (
        "You are a chunk-boundary planner for a retrieval system. You are given "
        "numbered paragraphs of ONE document section (with previews). Group "
        "CONSECUTIVE paragraphs into chunks so that each chunk covers a single "
        f"topic and is roughly {max_chars} characters in total (use the given "
        "sizes). Return ONLY the grouping as JSON: "
        '{"chunks": [[0,1],[2,3,4],[5]]} — every paragraph id exactly once, '
        "in order, no gaps. Do NOT return any text."
    )

    def _valid(groups, n: int) -> bool:
        """Strong id validation: a consecutive, complete partition of 0..n-1."""
        if not isinstance(groups, list) or not groups:
            return False
        flat = []
        for g in groups:
            if not isinstance(g, list) or not g:
                return False
            try:
                flat.extend(int(x) for x in g)
            except (TypeError, ValueError):
                return False
        return flat == list(range(n))

    def _boundaries(paras: list):
        payload = "\n".join(f"[{i}] ({len(p)} chars) {p[:_PREVIEW]}"
                            for i, p in enumerate(paras))
        data = llm_json(access, sys, payload)
        groups = (data or {}).get("chunks")
        if not _valid(groups, len(paras)):
            logger.info("[CHUNK-LLM] boundary grouping failed id validation → fallback")
            return None
        return [[int(x) for x in g] for g in groups]

    def _rebuild(paras: list, groups) -> list:
        if groups is None:
            return _fallback("\n\n".join(paras))
        out = []
        for g in groups:
            chunk = "\n\n".join(paras[i] for i in g)   # ORIGINAL text, verbatim
            if len(chunk) > max_chars * 2:             # model grouped too much
                out.extend(split_recursive(chunk, max_chars, 0))
            else:
                out.append(chunk)
        return out

    def _with_overlap(chunks: list) -> list:
        """Engine-side overlap: each chunk (after the first) starts with the
        tail of the previous one, cut at a word boundary."""
        ov = int(overlap or 0)
        if ov <= 0 or len(chunks) < 2:
            return chunks
        out = [chunks[0]]
        for prev, cur in zip(chunks, chunks[1:]):
            tail = prev[-ov:]
            sp = tail.find(" ")
            if 0 <= sp < len(tail) - 1:
                tail = tail[sp + 1:]
            out.append(f"{tail}\n{cur}" if tail else cur)
        return out

    def _split(text: str) -> list:
        if not text or not text.strip():
            return []
        text = text.strip()
        if len(text) <= int(max_chars * 1.3):
            return [text]                              # already chunk-sized
        # cost guard / no key → recursive (it carries its OWN overlap already,
        # so the engine overlap is only added to boundary-built chunks)
        if len(text) < _NO_LLM_UNDER or not access or not access.get("api_key"):
            return _fallback(text)
        paras = _paragraphs(text)
        if len(paras) < 2:
            return _fallback(text)
        # window paragraphs so one call never exceeds the token cap
        chunks, start, used_llm = [], 0, True
        while start < len(paras):
            win, wchars = [], 0
            while start + len(win) < len(paras):
                p = paras[start + len(win)]
                if win and wchars + len(p) > _MAX_LLM_TEXT:
                    break
                win.append(p)
                wchars += len(p)
            groups = _boundaries(win)
            if groups is None:
                used_llm = False
            chunks.extend(_rebuild(win, groups))
            start += len(win)
        if not chunks:
            return _fallback(text)
        return _with_overlap(chunks) if used_llm else chunks

    return _split
