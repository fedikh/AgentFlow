"""
Loaders — Entry point for the Ingestion Layer (Step 1).

Routes file extensions to the correct loader module.
Each loader returns a standardized dict:
    {
        "raw_text": str,
        "num_pages": int,
        "file_type": str,
        "category": str,       # "document" | "table" | "web"
        "metadata": dict,
        "total_chars": int,
    }

Usage:
    from loaders import load_document, load_from_url, SUPPORTED_FORMATS
    result = load_document("/tmp/upload.pdf")
    result = load_from_url("https://docs.company.com/api")
"""
import os
import logging

logger = logging.getLogger(__name__)

# ── Lazy imports — each loader is imported only when needed ──

SUPPORTED_FORMATS = {
    # Documents
    ".pdf":  {"loader": "app.services.providers.loaders.documents.pdf_loader",      "category": "document", "label": "PDF"},
    ".docx": {"loader": "app.services.providers.loaders.documents.docx_loader",     "category": "document", "label": "Word"},
    ".txt":  {"loader": "app.services.providers.loaders.documents.txt_loader",      "category": "document", "label": "Text"},
    ".md":   {"loader": "app.services.providers.loaders.documents.markdown_loader",  "category": "document", "label": "Markdown"},
    ".json": {"loader": "app.services.providers.loaders.documents.json_loader", "category": "document", "label": "JSON"},
    ".xml":  {"loader": "app.services.providers.loaders.documents.xml_loader",  "category": "document", "label": "XML"},
    ".pptx": {"loader": "app.services.providers.loaders.documents.pptx_loader", "category": "document", "label": "PPTX"},
    # Tabular
    ".csv":  {"loader": "app.services.providers.loaders.tabular.csv_loader",        "category": "table",    "label": "CSV"},
    ".xlsx": {"loader": "app.services.providers.loaders.tabular.excel_loader",      "category": "table",    "label": "Excel"},
    ".xls":  {"loader": "app.services.providers.loaders.tabular.excel_loader",      "category": "table",    "label": "Excel"},
    # Web
    ".html": {"loader": "app.services.providers.loaders.web.html_loader",           "category": "web",      "label": "HTML"},
    ".htm":  {"loader": "app.services.providers.loaders.web.html_loader",           "category": "web",      "label": "HTML"},
}


def get_supported_extensions() -> list[str]:
    return list(SUPPORTED_FORMATS.keys())


def load_document(file_path: str) -> dict:
    """
    Main entry point — detect format and call the right loader.

    Args:
        file_path: path to the uploaded file

    Returns:
        Standardized dict with raw_text, metadata, etc.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext not in SUPPORTED_FORMATS:
        supported = ", ".join(SUPPORTED_FORMATS.keys())
        raise ValueError(f"Format '{ext}' not supported. Accepted: {supported}")

    format_info = SUPPORTED_FORMATS[ext]
    module_path = format_info["loader"]

    logger.info(f"[LOADER] Dispatching {format_info['label']} → {module_path}")

    # Dynamic import of the correct loader
    import importlib
    loader_module = importlib.import_module(module_path)

    return loader_module.load(file_path)


def load_from_url(url: str) -> dict:
    """
    Load content from a URL using the URL loader.
    """
    from app.services.providers.loaders._utils import validate_url
    url = validate_url(url)

    from app.services.providers.loaders.web.url_loader import load
    return load(url)
