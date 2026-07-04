"""
Image summarizer — describes an image with a FIXED vision model (Gemini 2.5
Flash) so it can be embedded and retrieved as text (multi-vector RAG).

Key comes from VISION_API_KEY in .env (dedicated, not the space's key).
Model is fixed: gemini-2.5-flash (vision included, very cheap).

summarize_image(path) → a short text description used as text_for_embedding.
Fails soft: on any error returns "" so parsing never crashes on one image.
"""
import os
import base64
import logging

logger = logging.getLogger(__name__)

VISION_MODEL = "gemini-2.5-flash"

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


def summarize_image(image_path: str) -> str:
    """Return a text summary of the image, or '' on failure."""
    if not image_path or not os.path.exists(image_path):
        logger.warning(f"[VISION] image not found on disk: {image_path}")
        return ""

    from app.config import settings
    api_key = settings.VISION_API_KEY
    if not api_key:
        logger.warning("[VISION] VISION_API_KEY not set — skipping image summary")
        return ""

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage

        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        mime = _mime_for(image_path)

        llm = ChatGoogleGenerativeAI(
            model=VISION_MODEL,
            google_api_key=api_key,
            temperature=0.2,
        )
        message = HumanMessage(content=[
            {"type": "text", "text": SUMMARY_PROMPT},
            {"type": "image_url", "image_url": f"data:{mime};base64,{b64}"},
        ])
        resp = llm.invoke([message])
        summary = (resp.content or "").strip()
        logger.info(f"[VISION] Summarized {os.path.basename(image_path)} "
                    f"({len(summary)} chars)")
        return summary

    except Exception as e:
        logger.warning(f"[VISION] Failed to summarize {image_path}: {e}")
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
    """
    count = 0
    images = getattr(parsed_doc, "images", []) or []
    logger.info(f"[VISION] Summarizing {len(images)} image(s)…")

    # cache: same image_path summarized once (many pages reuse the same file)
    cache = {}

    for img in images:
        if _is_real_summary(img):
            continue  # already has a genuine description

        path = getattr(img, "image_path", "")
        if not path:
            continue

        if path in cache:
            summary = cache[path]
        else:
            summary = summarize_image(path)
            cache[path] = summary

        if summary:
            parts = []
            if getattr(img, "caption", ""):
                parts.append(f"Caption: {img.caption}")
            if getattr(img, "ocr_text", ""):
                parts.append(f"Text in image: {img.ocr_text}")
            parts.append(f"Description: {summary}")
            img.text_for_embedding = "\n".join(parts)
            count += 1

    logger.info(f"[VISION] Done: {count} image(s) summarized")
    return count