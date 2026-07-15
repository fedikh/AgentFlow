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
    Enterprise cleaning of the parsed_document (what goes to chunking / embedding
    / LLM). Per-section pipeline, in order:

        encoding fix → text normalize → OCR fix → HTML strip
        → structural noise removal → paragraph dedup → (optional) PII redact

    Then document-level: section dedup, language detection, PII detection.
    Each stage is toggleable via app.config.Settings (CLEAN_*), so behaviour is
    configurable without code changes. A per-stage report is written to metadata.
    """
    import time
    start = time.time()
    metadata = loaded_data.setdefault("metadata", {})

    try:
        from app.config import settings
    except Exception:
        settings = None

    def _flag(name, default):
        return bool(getattr(settings, name, default)) if settings else default

    do_noise  = _flag("CLEAN_REMOVE_NOISE", True)
    do_dedup  = _flag("CLEAN_DEDUP", True)
    do_html   = _flag("CLEAN_STRIP_HTML", True)
    do_pii_dt = _flag("CLEAN_DETECT_PII", True)
    do_pii_rx = _flag("CLEAN_REDACT_PII", False)

    # Only clean parsed_document — skip raw_text (just preview)
    if "parsed_document" in loaded_data and loaded_data["parsed_document"]:
        doc = loaded_data["parsed_document"]

        from app.services.providers.cleaners.encoding_cleaner import fix_encoding
        from app.services.providers.cleaners.text_cleaner import normalize_text, strip_html
        from app.services.providers.cleaners.document_cleaner import remove_noise
        from app.services.providers.cleaners.ocr_cleaner import fix_ocr
        from app.services.providers.cleaners.language_detector import detect_language
        from app.services.providers.cleaners.dedup_cleaner import (
            dedupe_paragraphs, dedupe_sections,
        )
        from app.services.providers.cleaners.pii_cleaner import detect_pii, redact_pii

        report = {"noise_removed": 0, "paragraphs_deduped": 0,
                  "sections_deduped": 0, "html_stripped": 0, "pii": {}}

        # ── Clean each section ──
        for sec in doc.get("sections", []):
            if sec.get("content"):
                c = sec["content"]
                c, _ = fix_encoding(c)
                c, _ = normalize_text(c)
                c, _ = fix_ocr(c)
                if do_html:
                    c, hf = strip_html(c)
                    report["html_stripped"] += len(hf)
                if do_noise:
                    c, nf = remove_noise(c)
                    report["noise_removed"] += len(nf)
                if do_dedup:
                    c, dr = dedupe_paragraphs(c)
                    report["paragraphs_deduped"] += dr
                if do_pii_rx:
                    c, pc = redact_pii(c)
                    for k, v in pc.items():
                        report["pii"][k] = report["pii"].get(k, 0) + v
                sec["content"] = c
            if sec.get("heading"):
                h, _ = fix_encoding(sec["heading"])
                h, _ = normalize_text(h)
                if do_html:
                    h, _ = strip_html(h)
                sec["heading"] = h

        # ── Section-level dedup (drop repeated boilerplate sections) ──
        if do_dedup:
            doc["sections"], report["sections_deduped"] = dedupe_sections(
                doc.get("sections", [])
            )

        # ── Clean each table (structure-preserving: no noise/dedup) ──
        for tab in doc.get("tables", []):
            if tab.get("content"):
                t, _ = fix_encoding(tab["content"])
                t, _ = normalize_text(t)
                if do_html:
                    t, _ = strip_html(t)
                tab["content"] = t

        # ── Clean the element-schema text (new format) ──
        # Light text cleanup on element bodies so the elements[] output is
        # production-clean. Structure (ids, hierarchy, tables' rows) is kept.
        def _clean_text_val(v):
            v, _ = fix_encoding(v)
            v, _ = normalize_text(v)
            v, _ = fix_ocr(v)          # match section-level OCR cleanup (hyphen
            if do_html:                # rejoin, garbage/control removal) so the
                v, _ = strip_html(v)   # elements[] format is as clean as sections
            return v

        for el in doc.get("elements", []):
            cont = el.get("content", {})
            if not isinstance(cont, dict):
                continue
            t = el.get("type")
            if t in ("heading", "paragraph", "list_item") and cont.get("text"):
                cont["text"] = _clean_text_val(cont["text"])
            elif t == "table":
                if cont.get("caption"):
                    cont["caption"], _ = fix_encoding(cont["caption"])
                    cont["caption"], _ = normalize_text(cont["caption"])
                for row in cont.get("rows", []):
                    if isinstance(row, dict):
                        for k in list(row.keys()):
                            if isinstance(row[k], str) and row[k]:
                                row[k] = _clean_text_val(row[k])

        # ── Detect language from sections ──
        all_text = " ".join(s.get("content", "") for s in doc.get("sections", []))
        if all_text.strip():
            lang, conf = detect_language(all_text)
            metadata["language"] = lang
            metadata["language_confidence"] = conf

            # ── PII detection (non-destructive) — count into metadata ──
            if do_pii_dt and not do_pii_rx:
                report["pii"] = detect_pii(all_text)

        # Recalculate total_chars
        total = sum(len(s.get("content", "")) + len(s.get("heading", "")) for s in doc.get("sections", []))
        total += sum(len(t.get("content", "")) for t in doc.get("tables", []))
        doc["total_chars"] = total

        loaded_data["parsed_document"] = doc
        metadata["cleaning_report"] = report

    elapsed = round(time.time() - start, 2)
    metadata.setdefault("cleaning", {})["time_seconds"] = elapsed
    logger.info(f"[CLEANER] Parsed document cleaned in {elapsed}s "
                f"({metadata.get('cleaning_report', {})})")

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