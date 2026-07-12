"""
Image summarizer — describes an image with a vision model so it can be embedded
and retrieved as text (multi-vector RAG).

Provider is configurable via settings (VISION_PROVIDER):
    openai  → ChatOpenAI          (default, gpt-4o-mini) — key = VISION_API_KEY
    gemini  → ChatGoogleGenerativeAI (gemini-2.5-flash)  — key = VISION_API_KEY
    ollama  → ChatOllama          (llava, local/offline) — no key, OLLAMA_BASE_URL

summarize_image(path) → a short text description used as text_for_embedding.
Fails soft: on any error returns "" so parsing never crashes on one image.
"""
import os
import base64
import logging

logger = logging.getLogger(__name__)

# Fallback model per provider when settings.VISION_MODEL is blank.
_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash",
    "ollama": "llava",
}

SUMMARY_PROMPT = (
    "You are describing an image extracted from a document so it can be "
    "found later by a search engine. Write a concise, factual description "
    "(2-4 sentences) capturing: what the image shows, any visible text, "
    "labels, numbers, chart/table data, and its likely purpose. "
    "Do not add commentary. Output only the description."
)


def _mime_for(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(ext, "image/png")


class VisionError(Exception):
    """Vision summarization failed. `quota` marks a 429 / RESOURCE_EXHAUSTED."""
    def __init__(self, message: str, quota: bool = False):
        super().__init__(message)
        self.quota = quota


def _is_quota_error(err) -> bool:
    s = str(err).lower()
    return ("429" in s or "resource_exhausted" in s or "insufficient_quota" in s
            or "quota" in s or "rate limit" in s or "rate-limit" in s
            or "rate_limit" in s)


def _resolve_vision():
    """Return (provider, model, api_key) from settings, with sane fallbacks."""
    from app.config import settings
    provider = (getattr(settings, "VISION_PROVIDER", "openai") or "openai").lower()
    model = getattr(settings, "VISION_MODEL", "") or _DEFAULT_MODELS.get(provider, "")
    api_key = getattr(settings, "VISION_API_KEY", "") or ""
    return provider, model, api_key


def _build_vision_llm(provider: str, model: str, api_key: str):
    """Build the langchain chat model for the selected vision provider."""
    # max_retries=0 → disable the client's own retry storm (defaults to ~6
    # exponential retries). We control retries ourselves so a dead quota fails
    # fast. timeout caps a hung network call.
    if provider == "openai":
        if not api_key:
            raise VisionError("VISION_API_KEY not set (OpenAI)")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, api_key=api_key, temperature=0.2,
                          max_retries=0, timeout=30)
    if provider == "gemini":
        if not api_key:
            raise VisionError("VISION_API_KEY not set (Gemini)")
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, google_api_key=api_key,
                                      temperature=0.2, max_retries=0, timeout=30)
    if provider == "ollama":
        from langchain_ollama import ChatOllama
        from app.config import settings
        return ChatOllama(model=model, base_url=settings.OLLAMA_BASE_URL,
                          temperature=0.2)
    raise VisionError(f"unknown VISION_PROVIDER '{provider}' "
                      f"(use openai | gemini | ollama)")


def _image_message(provider: str, mime: str, b64: str):
    """Build a multimodal HumanMessage; Gemini takes a string image_url, OpenAI
    (and Ollama, OpenAI-style) take an object."""
    from langchain_core.messages import HumanMessage
    if provider == "gemini":
        img_block = {"type": "image_url", "image_url": f"data:{mime};base64,{b64}"}
    else:
        img_block = {"type": "image_url",
                     "image_url": {"url": f"data:{mime};base64,{b64}"}}
    return HumanMessage(content=[
        {"type": "text", "text": SUMMARY_PROMPT},
        img_block,
    ])


def _summarize_or_raise(image_path: str, retries: int = 1, base_wait: float = 2.0) -> str:
    """
    Call the configured vision provider for one image. Retries on 429/rate-limit
    (per-minute limits recover); raises VisionError(quota=…) on final failure so
    the caller can react (e.g. stop hammering a dead quota) instead of silently
    getting ''.
    """
    if not image_path or not os.path.exists(image_path):
        raise VisionError(f"image not found on disk: {image_path}")

    import time as _time
    provider, model, api_key = _resolve_vision()

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    mime = _mime_for(image_path)

    llm = _build_vision_llm(provider, model, api_key)
    message = _image_message(provider, mime, b64)

    last = None
    for attempt in range(retries + 1):
        try:
            resp = llm.invoke([message])
            summary = (resp.content or "").strip()
            logger.info(f"[VISION] Summarized {os.path.basename(image_path)} "
                        f"({len(summary)} chars)")
            return summary
        except Exception as e:
            last = e
            if _is_quota_error(e) and attempt < retries:
                wait = base_wait * (attempt + 1)
                logger.warning(f"[VISION] 429 rate-limited; retry "
                               f"{attempt + 1}/{retries} in {wait:.0f}s")
                _time.sleep(wait)
                continue
            break

    raise VisionError(str(last), quota=_is_quota_error(last))


def summarize_image(image_path: str) -> str:
    """Return a text summary of the image, or '' on failure (never raises)."""
    try:
        return _summarize_or_raise(image_path)
    except VisionError as e:
        logger.warning(f"[VISION] Failed to summarize "
                       f"{os.path.basename(image_path or '')}: {e}")
        return ""


def _is_real_summary(img) -> bool:
    """
    True if the image already has a REAL Gemini summary (not just the caption).
    The loader pre-fills text_for_embedding with the caption (e.g. "Image on
    page 4"), so we must NOT treat that as an existing summary.
    """
    tfe = (getattr(img, "text_for_embedding", "") or "").strip()
    caption = (getattr(img, "caption", "") or "").strip()
    if not tfe:
        return False
    # if text_for_embedding is just the caption (or shorter than a sentence),
    # it's not a real summary → we still want to summarize
    if tfe == caption:
        return False
    if tfe.startswith("Image on page"):
        return False
    if len(tfe) < 40:   # a real description is longer than a caption
        return False
    return True


def summarize_images_in_parsed(parsed_doc) -> int:
    """
    Fill text_for_embedding on every image with a REAL Gemini description.
    Skips images that already have a genuine summary. Returns count summarized.
    Mutates parsed_doc in place.

    Images are summarized CONCURRENTLY (thread pool) — each summary is an
    independent network call to Gemini, so doing them serially was the dominant
    cost of load+parse on image-heavy documents. Each unique image_path is
    summarized once (many pages can reference the same file).
    """
    from concurrent.futures import ThreadPoolExecutor

    images = getattr(parsed_doc, "images", []) or []
    todo = [img for img in images if not _is_real_summary(img)
            and getattr(img, "image_path", "")]
    logger.info(f"[VISION] Summarizing {len(todo)}/{len(images)} image(s)…")
    if not todo:
        return 0

    # Unique paths → one Gemini call each.
    unique_paths = list({img.image_path for img in todo})
    try:
        from app.config import settings
        workers = max(1, int(settings.VISION_MAX_WORKERS))
    except Exception:
        workers = 6
    workers = min(workers, len(unique_paths))

    meta = getattr(parsed_doc, "metadata", None)
    if not isinstance(meta, dict):
        meta = {}
        try:
            parsed_doc.metadata = meta
        except Exception:
            pass

    # ── Pre-flight probe: one synchronous call. If the quota is dead / key is
    # bad, bail out immediately with a clear reason instead of firing a whole
    # parallel burst that all 429s (and hangs on retries). ──
    try:
        first_summary = _summarize_or_raise(unique_paths[0])
    except VisionError as e:
        reason = "quota_exceeded" if e.quota else "vision_error"
        meta["vision"] = {"summarized": 0, "total": len(unique_paths),
                          "reason": reason, "detail": str(e)[:200]}
        logger.warning(f"[VISION] Skipping image summaries — {reason}: {e}")
        return 0

    summaries = {unique_paths[0]: first_summary}
    rest = unique_paths[1:]
    if rest:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            summaries.update(dict(zip(rest, pool.map(summarize_image, rest))))

    count = 0
    for img in todo:
        summary = summaries.get(img.image_path, "")
        if summary:
            parts = []
            if getattr(img, "caption", ""):
                parts.append(f"Caption: {img.caption}")
            if getattr(img, "ocr_text", ""):
                parts.append(f"Text in image: {img.ocr_text}")
            parts.append(f"Description: {summary}")
            img.text_for_embedding = "\n".join(parts)
            count += 1

    # Keep the element-schema image blocks in sync with their descriptions.
    for el in getattr(parsed_doc, "elements", []) or []:
        if el.get("type") != "image":
            continue
        cont = el.get("content", {})
        summary = summaries.get(cont.get("image_path", ""), "")
        if not summary:
            continue
        parts = []
        if cont.get("caption"):
            parts.append(f"Caption: {cont['caption']}")
        if cont.get("ocr_text"):
            parts.append(f"Text in image: {cont['ocr_text']}")
        parts.append(f"Description: {summary}")
        cont["text_for_embedding"] = "\n".join(parts)

    meta["vision"] = {"summarized": count, "total": len(unique_paths)}
    if count < len(unique_paths):
        meta["vision"]["note"] = ("some images not described — vision API limit "
                                  "or transient error")
    logger.info(f"[VISION] Done: {count}/{len(unique_paths)} image(s) summarized "
                f"({workers} workers)")
    return count