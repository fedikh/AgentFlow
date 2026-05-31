"""
Processing Factory — point d'entrée unique pour l'extraction de contenu.

Usage dans rag_service.py :
    from app.services.providers.processing_factory import extract_document, extract_from_url, SUPPORTED_FORMATS

    # Upload fichier local
    blocks = extract_document(file_path)

    # Scraping URL
    blocks = extract_from_url("https://docs.company.com/api")
"""
import os
import logging

logger = logging.getLogger(__name__)

# ── Import des processeurs ──
from app.services.providers.processing_factory.document_processors import (
    extract_pdf, extract_docx, extract_txt, extract_markdown,
)
from app.services.providers.processing_factory.table_processors import (
    extract_csv, extract_xlsx,
)
from app.services.providers.processing_factory.web_processors import (
    extract_html, extract_url,
)
from app.services.providers.processing_factory.upload_sources import (
    save_uploaded_file, cleanup_temp_file, validate_url, get_url_filename,
)


# ══════════════════════════════════════════════════════
# FORMATS SUPPORTÉS
# ══════════════════════════════════════════════════════

SUPPORTED_FORMATS = {
    # Documents
    ".pdf":  {"processor": extract_pdf,      "category": "document", "label": "PDF"},
    ".docx": {"processor": extract_docx,     "category": "document", "label": "Word"},
    ".doc":  {"processor": extract_docx,     "category": "document", "label": "Word"},
    ".txt":  {"processor": extract_txt,      "category": "document", "label": "Text"},
    ".md":   {"processor": extract_markdown, "category": "document", "label": "Markdown"},

    # Données tabulaires
    ".csv":  {"processor": extract_csv,      "category": "table",    "label": "CSV"},
    ".xlsx": {"processor": extract_xlsx,     "category": "table",    "label": "Excel"},
    ".xls":  {"processor": extract_xlsx,     "category": "table",    "label": "Excel"},

    # Web
    ".html": {"processor": extract_html,     "category": "web",      "label": "HTML"},
    ".htm":  {"processor": extract_html,     "category": "web",      "label": "HTML"},
}


def get_supported_extensions() -> list[str]:
    """Retourne la liste des extensions supportées."""
    return list(SUPPORTED_FORMATS.keys())


def get_supported_formats_info() -> list[dict]:
    """Retourne les infos sur chaque format (pour le frontend)."""
    seen = set()
    result = []
    for ext, info in SUPPORTED_FORMATS.items():
        if info["label"] not in seen:
            seen.add(info["label"])
            result.append({
                "extension": ext,
                "label": info["label"],
                "category": info["category"],
            })
    return result


# ══════════════════════════════════════════════════════
# EXTRACT DOCUMENT (fichier local)
# ══════════════════════════════════════════════════════

def extract_document(file_path: str) -> list[dict]:
    """
    Point d'entrée unique pour les fichiers locaux.
    Détecte le format par extension et appelle le bon processeur.

    Args:
        file_path: chemin vers le fichier temporaire

    Returns:
        list[dict] — [{type: "text"/"table", content: str, page: int}]
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext not in SUPPORTED_FORMATS:
        supported = ", ".join(SUPPORTED_FORMATS.keys())
        raise ValueError(f"Format '{ext}' non supporté. Acceptés : {supported}")

    format_info = SUPPORTED_FORMATS[ext]
    processor = format_info["processor"]

    logger.info(f"Extracting {format_info['label']} ({format_info['category']}): {os.path.basename(file_path)}")

    blocks = processor(file_path)

    # Post-processing : nettoyer les blocs vides
    cleaned = []
    for block in blocks:
        content = block.get("content", "").strip()
        if content and len(content) > 10:
            cleaned.append({
                "type": block.get("type", "text"),
                "content": content,
                "page": block.get("page", 1),
            })

    logger.info(f"Extracted {len(cleaned)} blocks ({sum(1 for b in cleaned if b['type']=='text')} text, {sum(1 for b in cleaned if b['type']=='table')} tables)")

    return cleaned


# ══════════════════════════════════════════════════════
# EXTRACT FROM URL (scraping web)
# ══════════════════════════════════════════════════════

def extract_from_url(url: str) -> list[dict]:
    """
    Point d'entrée pour le scraping d'URL.
    Télécharge la page et extrait le contenu.

    Args:
        url: URL complète (https://...)

    Returns:
        list[dict] — [{type: "text"/"table", content: str, page: int}]
    """
    url = validate_url(url)

    logger.info(f"Scraping URL: {url}")

    blocks = extract_url(url)

    # Post-processing
    cleaned = []
    for block in blocks:
        content = block.get("content", "").strip()
        if content and len(content) > 10:
            cleaned.append({
                "type": block.get("type", "text"),
                "content": content,
                "page": block.get("page", 1),
            })

    logger.info(f"Scraped {len(cleaned)} blocks from {url}")

    return cleaned
