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
    """Clean only the parsed_document (what goes to chunking/embedding/LLM)."""
    import time
    start = time.time()
    metadata = loaded_data.setdefault("metadata", {})

    # Only clean parsed_document — skip raw_text (just preview)
    if "parsed_document" in loaded_data and loaded_data["parsed_document"]:
        doc = loaded_data["parsed_document"]
        report = {}

        from app.services.providers.cleaners.encoding_cleaner import fix_encoding
        from app.services.providers.cleaners.text_cleaner import normalize_text
        from app.services.providers.cleaners.document_cleaner import remove_noise
        from app.services.providers.cleaners.ocr_cleaner import fix_ocr
        from app.services.providers.cleaners.language_detector import detect_language

        # Clean each section
        for sec in doc.get("sections", []):
            if sec.get("content"):
                sec["content"], f = fix_encoding(sec["content"])
                sec["content"], f2 = normalize_text(sec["content"])
                sec["content"], f3 = fix_ocr(sec["content"])
            if sec.get("heading"):
                sec["heading"], _ = fix_encoding(sec["heading"])
                sec["heading"], _ = normalize_text(sec["heading"])

        # Clean each table
        for tab in doc.get("tables", []):
            if tab.get("content"):
                tab["content"], _ = fix_encoding(tab["content"])
                tab["content"], _ = normalize_text(tab["content"])

        # Detect language from sections
        all_text = " ".join(s.get("content", "") for s in doc.get("sections", []))
        if all_text.strip():
            lang, conf = detect_language(all_text)
            metadata["language"] = lang
            metadata["language_confidence"] = conf

        # Recalculate total_chars
        total = sum(len(s.get("content", "")) + len(s.get("heading", "")) for s in doc.get("sections", []))
        total += sum(len(t.get("content", "")) for t in doc.get("tables", []))
        doc["total_chars"] = total

        loaded_data["parsed_document"] = doc

    elapsed = round(time.time() - start, 2)
    metadata["cleaning"] = {"time_seconds": elapsed}
    logger.info(f"[CLEANER] Parsed document cleaned in {elapsed}s")

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