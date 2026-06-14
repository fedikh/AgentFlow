"""
Document Loaders — PDF, DOCX, TXT, Markdown.

Each loader uses LlamaIndex and returns:
    {"raw_text": str, "num_pages": int, "file_type": str,
     "category": "document", "metadata": dict, "total_chars": int}
"""
from app.services.providers.loaders.documents.pdf_loader import load as load_pdf
from app.services.providers.loaders.documents.docx_loader import load as load_docx
from app.services.providers.loaders.documents.txt_loader import load as load_txt
from app.services.providers.loaders.documents.markdown_loader import load as load_markdown

__all__ = ["load_pdf", "load_docx", "load_txt", "load_markdown"]
