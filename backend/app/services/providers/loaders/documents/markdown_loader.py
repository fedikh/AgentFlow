"""
Markdown Loader — uses LlamaIndex SimpleDirectoryReader.
"""
import os
import logging
from llama_index.core import SimpleDirectoryReader

logger = logging.getLogger(__name__)


def load(file_path: str) -> dict:
    logger.info(f"[MD_LOADER] Loading: {os.path.basename(file_path)}")

    reader = SimpleDirectoryReader(input_files=[file_path])
    documents = reader.load_data()

    if not documents:
        raise ValueError("Markdown file is empty")

    raw_text = "\n\n".join(doc.text for doc in documents if doc.text.strip())

    from app.services.providers.loaders._utils import clean_text
    raw_text = clean_text(raw_text)

    if not raw_text.strip():
        raise ValueError("Markdown loaded but no text extracted")

    metadata = {}
    if documents and hasattr(documents[0], "metadata") and documents[0].metadata:
        from app.services.providers.loaders._utils import sanitize_metadata
        metadata = sanitize_metadata(documents[0].metadata)

    return {
        "raw_text": raw_text,
        "num_pages": 1,
        "file_type": "Markdown",
        "category": "document",
        "metadata": metadata,
        "total_chars": len(raw_text),
    }
