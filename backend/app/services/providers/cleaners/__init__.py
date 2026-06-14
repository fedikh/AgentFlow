"""
══════════════════════════════════════════════════════════════
  Cleaning Layer — Enterprise Document Preprocessing Pipeline
══════════════════════════════════════════════════════════════

Packages used:
  ftfy        → encoding normalization (mojibake fix)
  clean-text  → URL/email/emoji removal, text normalization
  langdetect  → language detection
  unidecode   → Unicode to ASCII transliteration
  chardet     → encoding detection

Pipeline position:
  Upload → Loader → ★ CLEANER ★ → Parser → Chunking → Embedding

pip install ftfy clean-text langdetect unidecode
"""
import logging
import time

logger = logging.getLogger(__name__)


def clean_loaded_data(loaded_data: dict) -> dict:
    """
    Run all 5 cleaning steps on loaded_data.
    Cleans raw_text AND parsed_document sections if present.
    """
    start = time.time()

    raw_text = loaded_data.get("raw_text", "")
    if not raw_text:
        return loaded_data

    original_len = len(raw_text)
    metadata = loaded_data.setdefault("metadata", {})
    report = {}

    # Step 1: Encoding fix (ftfy)
    from app.services.providers.cleaners.encoding_cleaner import fix_encoding
    raw_text, fixes = fix_encoding(raw_text)
    if fixes: report["encoding"] = fixes

    # Step 2: Text normalization (clean-text + unidecode)
    from app.services.providers.cleaners.text_cleaner import normalize_text
    raw_text, fixes = normalize_text(raw_text)
    if fixes: report["text"] = fixes

    # Step 3: Document noise removal
    from app.services.providers.cleaners.document_cleaner import remove_noise
    raw_text, fixes = remove_noise(raw_text)
    if fixes: report["noise"] = fixes

    # Step 4: OCR artifact fix
    from app.services.providers.cleaners.ocr_cleaner import fix_ocr
    raw_text, fixes = fix_ocr(raw_text)
    if fixes: report["ocr"] = fixes

    # Step 5: Language detection (langdetect)
    from app.services.providers.cleaners.language_detector import detect_language
    lang, confidence = detect_language(raw_text)
    metadata["language"] = lang
    metadata["language_confidence"] = confidence

    # Update loaded_data
    loaded_data["raw_text"] = raw_text
    loaded_data["total_chars"] = len(raw_text)

    # Clean parsed_document if present (PDF/DOCX/PPTX)
    if "parsed_document" in loaded_data and loaded_data["parsed_document"]:
        loaded_data["parsed_document"] = _clean_parsed_document(loaded_data["parsed_document"])

    # Report
    removed = original_len - len(raw_text)
    elapsed = round(time.time() - start, 2)
    metadata["cleaning"] = {
        "chars_before": original_len,
        "chars_after": len(raw_text),
        "chars_removed": removed,
        "reduction_percent": round((removed / original_len) * 100, 1) if original_len else 0,
        "time_seconds": elapsed,
        "fixes": report,
    }

    logger.info(
        f"[CLEANER] {elapsed}s — {original_len}→{len(raw_text)} chars "
        f"(-{removed}, {metadata['cleaning']['reduction_percent']}%) "
        f"lang={lang}"
    )

    return loaded_data


def _clean_parsed_document(doc: dict) -> dict:
    """Clean text inside parsed sections and tables."""
    from app.services.providers.cleaners.encoding_cleaner import fix_encoding
    from app.services.providers.cleaners.text_cleaner import normalize_text

    for sec in doc.get("sections", []):
        if sec.get("content"):
            sec["content"], _ = fix_encoding(sec["content"])
            sec["content"], _ = normalize_text(sec["content"])
        if sec.get("heading"):
            sec["heading"], _ = fix_encoding(sec["heading"])
            sec["heading"], _ = normalize_text(sec["heading"])

    for tab in doc.get("tables", []):
        if tab.get("content"):
            tab["content"], _ = fix_encoding(tab["content"])
            tab["content"], _ = normalize_text(tab["content"])

    total = sum(len(s.get("content", "")) + len(s.get("heading", "")) for s in doc.get("sections", []))
    total += sum(len(t.get("content", "")) for t in doc.get("tables", []))
    doc["total_chars"] = total

    return doc