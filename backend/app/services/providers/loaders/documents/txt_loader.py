"""
TXT Loader — uses LlamaIndex with encoding detection fallback.
"""
import os
import logging
from llama_index.core import SimpleDirectoryReader

logger = logging.getLogger(__name__)


def load(file_path: str) -> dict:
    logger.info(f"[TXT_LOADER] Loading: {os.path.basename(file_path)}")

    reader = SimpleDirectoryReader(input_files=[file_path])
    documents = reader.load_data()

    if not documents:
        documents = _fallback_read(file_path)

    raw_text = "\n\n".join(doc.text for doc in documents if doc.text.strip())

    from app.services.providers.loaders._utils import clean_text
    raw_text = clean_text(raw_text)

    if not raw_text.strip():
        raise ValueError("Text file is empty")

    metadata = {}
    if documents and hasattr(documents[0], "metadata") and documents[0].metadata:
        from app.services.providers.loaders._utils import sanitize_metadata
        metadata = sanitize_metadata(documents[0].metadata)

    return {
        "raw_text": raw_text,
        "num_pages": 1,
        "file_type": "Text",
        "category": "document",
        "metadata": metadata,
        "total_chars": len(raw_text),
    }


def _fallback_read(file_path):
    from llama_index.core.schema import Document as LIDocument
    import chardet
    with open(file_path, "rb") as f:
        raw = f.read()
    detected = chardet.detect(raw)
    encoding = detected.get("encoding", "utf-8") or "utf-8"
    text = raw.decode(encoding, errors="replace")
    return [LIDocument(text=text, metadata={"source": file_path})]
