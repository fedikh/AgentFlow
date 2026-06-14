"""
Parsers — Entry point for the Ingestion Layer (Step 2).
Every parser produces a ParsedDocument.
"""
import logging

logger = logging.getLogger(__name__)

PARSER_REGISTRY = {
    ("document", "PDF"):      "app.services.providers.parsers.documents.pdf_parser",
    ("document", "Word"):     "app.services.providers.parsers.documents.docx_parser",
    ("document", "Text"):     "app.services.providers.parsers.documents.txt_parser",
    ("document", "Markdown"): "app.services.providers.parsers.documents.markdown_parser",
    ("document", "PPTX"): "app.services.providers.parsers.documents.pptx_parser",
    ("table", "CSV"):         "app.services.providers.parsers.tabular.csv_parser",
    ("document", "JSON"): "app.services.providers.parsers.documents.json_parser",
    ("document", "XML"):  "app.services.providers.parsers.documents.xml_parser",
    ("table", "Excel"):       "app.services.providers.parsers.tabular.excel_parser",
    ("web", "HTML"):          "app.services.providers.parsers.web.html_parser",
    
}


def parse_document(loaded_data: dict):
    # Import INSIDE function to avoid circular import
    from app.services.providers.parsers.parsed_document import ParsedDocument, Section

    category = loaded_data.get("category", "document")
    file_type = loaded_data.get("file_type", "Text")
    raw_text = loaded_data.get("raw_text", "")

    if not raw_text.strip():
        raise ValueError("No text to parse")

    key = (category, file_type)
    module_path = PARSER_REGISTRY.get(key)

    if not module_path:
        logger.warning(f"[PARSER] No parser for {key}, returning raw")
        return ParsedDocument(
            sections=[Section(heading="", content=raw_text, page=1)],
            file_type=file_type,
            category=category,
        )

    logger.info(f"[PARSER] Dispatching {file_type} ({category}) → {module_path}")

    import importlib
    parser_module = importlib.import_module(module_path)
    parsed_doc = parser_module.parse(loaded_data)

    logger.info(f"[PARSER] → {parsed_doc.total_sections} sections, "
                f"{parsed_doc.total_tables} tables, "
                f"{parsed_doc.total_images} images")

    return parsed_doc