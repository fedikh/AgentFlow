"""
RAG Service v7 — LLM Factory Edition

CHANGES from v6:
  - generate_answer() removed (the hardcoded Groq one).
  - Now imports generate_answer from app.services.llm_factory.
  - query() calls generate_answer(db, space, question, context, sources_text)
    → the LLM provider/model/key/prompt are now resolved from the space config
      (space's own key → company provider → local GROQ fallback).

Everything else (loaders, parsers, chunking, embedding, search) is UNCHANGED.
"""

import os
import json
import tempfile
from collections import Counter
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException, UploadFile

from app.models.rag_space import RAGSpace
from app.models.document import Document, DocStatus
from app.models.chunk import Chunk
from app.schemas.rag import CreateRAGSpaceRequest, UpdateRAGSpaceRequest, QueryRequest
from app.config import settings

# ── Modular Loaders & Parsers ──
from app.services.providers.loaders import (
    load_document as li_load_document,
    load_from_url as li_load_from_url,
    SUPPORTED_FORMATS,
)
from app.services.providers.loaders._utils import validate_url, get_url_filename
from app.services.providers.parsers import parse_document as li_parse_document

# ── Chunking factory ──
from app.services.providers.chunking_factory import chunk_document

# ── LLM Factory (NEW) — replaces the hardcoded Groq generate_answer ──
from app.services.llm_factory import generate_answer

# ── Embeddings (UNCHANGED) ──
_embed_model = None

def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        os.environ["TRANSFORMERS_NO_TF"] = "1"
        os.environ["USE_TF"] = "0"
        from sentence_transformers import SentenceTransformer
        try:
            print("Loading BGE-M3 model...")
            _embed_model = SentenceTransformer("BAAI/bge-m3")
            print("✅ BGE-M3 loaded (1024 dims)")
        except Exception as e1:
            print(f"⚠️ BGE-M3 failed: {e1}")
            try:
                _embed_model = SentenceTransformer("BAAI/bge-base-en-v1.5")
                print("✅ BGE-base loaded (768 dims)")
            except Exception:
                _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
                print("✅ all-MiniLM loaded (384 dims)")
    return _embed_model


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = _get_embed_model()
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return [e.tolist() for e in embeddings]

def embed_query(text: str) -> list[float]:
    model = _get_embed_model()
    embedding = model.encode("Represent this sentence: " + text, show_progress_bar=False, normalize_embeddings=True)
    return embedding.tolist()


# ══════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════

def _find_space(db: Session, space_id: str, org_id: str) -> RAGSpace:
    space = db.query(RAGSpace).filter(RAGSpace.id == space_id, RAGSpace.organization_id == org_id).first()
    if not space:
        raise HTTPException(404, "RAG Space not found")
    return space


def _space_dict(db, space):
    num_docs = db.query(Document).filter(Document.rag_space_id == space.id).count()
    num_chunks = db.query(Chunk).filter(Chunk.rag_space_id == space.id).count()
    return {
        "id": space.id, "name": space.name, "description": space.description,
        "status": getattr(space, 'status', 'DRAFT') or 'DRAFT',
        "organization_id": space.organization_id,
        "department_id": space.department_id,
        "chunk_size": space.chunk_size, "chunk_overlap": space.chunk_overlap,
        "chunk_strategy": space.chunk_strategy,
        "chunk_mode": getattr(space, 'chunk_mode', 'FIXED_ALL') or 'FIXED_ALL',
        "embedding_provider": getattr(space, 'embedding_provider', 'LOCAL') or 'LOCAL',
        "embedding_model": getattr(space, 'embedding_model', 'BAAI/bge-m3') or 'BAAI/bge-m3',
        "llm_provider": getattr(space, 'llm_provider', 'GROQ') or 'GROQ',
        "llm_model": getattr(space, 'llm_model', 'llama-3.3-70b-versatile') or 'llama-3.3-70b-versatile',
        "llm_temperature": getattr(space, 'llm_temperature', 0.2) if getattr(space, 'llm_temperature', None) is not None else 0.2,
        "llm_max_tokens": getattr(space, 'llm_max_tokens', 1024) or 1024,
        # NEW: provider source for the IT selector (safe getattr — may not exist yet)
        "llm_provider_id": getattr(space, 'llm_provider_id', None),
        "llm_has_own_key": bool(getattr(space, 'llm_api_key_enc', None)),
        "top_k": space.top_k,
        "search_engine": getattr(space, 'search_engine', 'HYBRID') or 'HYBRID',
        "semantic_weight": getattr(space, 'semantic_weight', 0.7) if getattr(space, 'semantic_weight', None) is not None else 0.7,
        "reranking_enabled": getattr(space, 'reranking_enabled', False) or False,
        "system_prompt": getattr(space, 'system_prompt', None),
        "num_documents": num_docs, "num_chunks": num_chunks,
        "created_at": str(space.created_at),
    }

def _doc_dict(doc):
    status = doc.status.value if hasattr(doc.status, 'value') else str(doc.status)
    return {
        "id": doc.id, "file_name": doc.file_name, "file_type": doc.file_type,
        "file_size": doc.file_size,
        "source_type": getattr(doc, 'source_type', 'local') or 'local',
        "source_url": getattr(doc, 'source_url', None),
        "num_chunks": doc.num_chunks, "status": status, "error_msg": doc.error_msg,
        "chunk_strategy": getattr(doc, 'chunk_strategy', None),
        "chosen_strategy": getattr(doc, 'chosen_strategy', None),
        "has_loaded_content": bool(doc.loaded_content) if hasattr(doc, 'loaded_content') else False,
        "has_extracted_content": bool(doc.extracted_content) if hasattr(doc, 'extracted_content') else False,
        "rag_space_id": doc.rag_space_id, "uploaded_at": str(doc.uploaded_at),
    }


# ══════════════════════════════════════════════════════
# SPACES CRUD
# ══════════════════════════════════════════════════════

def create_space(db: Session, data: CreateRAGSpaceRequest, org_id: str, user) -> dict:
    space = RAGSpace(
        name=data.name, description=data.description or "",
        organization_id=org_id, department_id=data.department_id,
        chunk_size=data.chunk_size or 512, chunk_overlap=data.chunk_overlap or 50,
        chunk_strategy=data.chunk_strategy or "FIXED",
        chunk_mode=getattr(data, 'chunk_mode', None) or "FIXED_ALL",
    )
    db.add(space)
    db.commit()
    db.refresh(space)
    return _space_dict(db, space)

def list_spaces(db: Session, org_id: str, user) -> list:
    spaces = db.query(RAGSpace).filter(RAGSpace.organization_id == org_id).all()
    return [_space_dict(db, s) for s in spaces]

def get_space(db: Session, space_id: str, org_id: str) -> dict:
    space = _find_space(db, space_id, org_id)
    return _space_dict(db, space)

def update_space(db: Session, space_id: str, org_id: str, data: UpdateRAGSpaceRequest) -> dict:
    space = _find_space(db, space_id, org_id)
    payload = data.dict(exclude_unset=True)
 
    # Chiffre la clé propre de l'IT si fournie (jamais stockée en clair)
    if "llm_api_key" in payload:
        raw = payload.pop("llm_api_key")
        if raw:
            from app.services.providers_crypto import encrypt_key
            space.llm_api_key_enc = encrypt_key(raw)
        else:
            space.llm_api_key_enc = None   # clé vidée
 
    for field, value in payload.items():
        if value is not None:
            setattr(space, field, value)
 
    db.commit()
    db.refresh(space)
    return _space_dict(db, space)

def delete_space(db: Session, space_id: str, org_id: str) -> dict:
    space = _find_space(db, space_id, org_id)
    db.delete(space)
    db.commit()
    return {"message": f"Space '{space.name}' deleted"}

def list_documents(db: Session, space_id: str, org_id: str) -> list:
    _find_space(db, space_id, org_id)
    docs = db.query(Document).filter(Document.rag_space_id == space_id).order_by(Document.uploaded_at.desc()).all()
    return [_doc_dict(d) for d in docs]

def delete_document(db: Session, space_id: str, doc_id: str, org_id: str) -> dict:
    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    if doc.loaded_content:
        try:
            loaded = json.loads(doc.loaded_content)
            fp = loaded.get("file_path", "")
            if fp and os.path.exists(fp):
                os.unlink(fp)
        except Exception:
            pass

    db.delete(doc)
    db.commit()
    return {"message": f"Document '{doc.file_name}' deleted"}

def list_chunks(db: Session, space_id: str, doc_id: str, org_id: str) -> list:
    _find_space(db, space_id, org_id)
    chunks = db.query(Chunk).filter(Chunk.document_id == doc_id).order_by(Chunk.chunk_index).all()
    return [{"id": c.id, "content": c.content, "page": c.page, "chunk_index": c.chunk_index} for c in chunks]


# ══════════════════════════════════════════════════════
# PER-DOCUMENT STRATEGY
# ══════════════════════════════════════════════════════

def set_document_strategy(db: Session, space_id: str, doc_id: str, strategy: str, org_id: str) -> dict:
    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.rag_space_id == space_id,
    ).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    if strategy not in ("FIXED", "SEMANTIC", "HIERARCHICAL"):
        raise HTTPException(400, "Invalid strategy")

    doc.chunk_strategy = strategy
    db.commit()
    db.refresh(doc)
    return _doc_dict(doc)


# ══════════════════════════════════════════════════════
# STEP 1: UPLOAD
# ══════════════════════════════════════════════════════
async def upload_document(db: Session, space_id: str, org_id: str, file: UploadFile) -> dict:
    space = _find_space(db, space_id, org_id)

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED_FORMATS:
        supported = ", ".join(SUPPORTED_FORMATS.keys())
        raise HTTPException(400, f"Format '{ext}' not supported. Accepted: {supported}")

    content = await file.read()

    doc = Document(
        file_name=file.filename,
        file_type=ext.replace(".", ""),
        file_size=len(content),
        source_type="local",
        status=DocStatus.UPLOADING,
        rag_space_id=space_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    upload_dir = os.path.join("uploads", space_id)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{doc.id}{ext}")

    with open(file_path, "wb") as f:
        f.write(content)

    if ext in (".pdf", ".docx"):
        doc.loaded_content = json.dumps({"file_path": os.path.abspath(file_path)}, ensure_ascii=False)
        db.commit()
        db.refresh(doc)
        return _doc_dict(doc)

    try:
        loaded_data = li_load_document(file_path)

        from app.services.providers.cleaners import clean_loaded_data
        loaded_data = clean_loaded_data(loaded_data)

        if not loaded_data or not loaded_data.get("raw_text"):
            raise Exception("No content found in document")

        loaded_data["file_path"] = os.path.abspath(file_path)

        parsed_doc_data = loaded_data.pop("parsed_document", None)
        doc.loaded_content = json.dumps(loaded_data, ensure_ascii=False, default=str)

        if parsed_doc_data:
            doc.extracted_content = json.dumps(parsed_doc_data, ensure_ascii=False)
            doc.status = DocStatus.EXTRACTED
        else:
            doc.status = DocStatus.LOADED

        db.commit()
        db.refresh(doc)

    except Exception as e:
        doc.status = DocStatus.ERROR
        doc.error_msg = str(e)
        db.commit()
        if os.path.exists(file_path):
            os.unlink(file_path)
        raise HTTPException(500, f"Loading failed: {str(e)}")

    return _doc_dict(doc)


async def upload_from_drive(db, space_id, org_id, drive_file_id, access_token):
    import uuid
    from app.services.providers.google_drive import download_from_drive

    space = _find_space(db, space_id, org_id)

    doc_id = str(uuid.uuid4())
    save_dir = os.path.join("uploads", space_id)

    try:
        drive_result = download_from_drive(drive_file_id, access_token, save_dir)
    except Exception as e:
        raise HTTPException(500, f"Google Drive download failed: {e}")

    file_path = drive_result["file_path"]
    file_name = drive_result["file_name"]
    file_size = drive_result["file_size"]
    ext = os.path.splitext(file_name)[1].lower()

    doc = Document(
        id=doc_id,
        rag_space_id=space_id,
        file_name=file_name,
        file_type=ext.replace(".", ""),
        file_size=file_size,
        source_type="google_drive",
        status=DocStatus.UPLOADING,
    )
    db.add(doc)
    db.commit()

    doc.loaded_content = json.dumps({"file_path": os.path.abspath(file_path)}, ensure_ascii=False)
    db.commit()
    db.refresh(doc)

    return _doc_dict(doc)

# ══════════════════════════════════════════════════════
# STEP 2: LOAD + PARSE
# ══════════════════════════════════════════════════════

def load_and_parse_document(db, space_id, doc_id, org_id):
    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    file_path = None
    if doc.loaded_content:
        try:
            data = json.loads(doc.loaded_content)
            file_path = data.get("file_path")
        except Exception:
            pass

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(400, "File not found — re-upload the document")

    try:
        loaded_data = li_load_document(file_path)

        from app.services.providers.cleaners import clean_loaded_data
        loaded_data = clean_loaded_data(loaded_data)

        if not loaded_data or not loaded_data.get("raw_text"):
            raise Exception("No content found in document")

        loaded_data["file_path"] = os.path.abspath(file_path)

        parsed_doc_data = loaded_data.pop("parsed_document", None)

        doc.loaded_content = json.dumps(loaded_data, ensure_ascii=False, default=str)

        if parsed_doc_data:
            doc.extracted_content = json.dumps(parsed_doc_data, ensure_ascii=False)
            doc.status = DocStatus.EXTRACTED
        else:
            doc.status = DocStatus.LOADED

        db.commit()
        db.refresh(doc)

    except Exception as e:
        doc.status = DocStatus.ERROR
        doc.error_msg = str(e)[:500]
        db.commit()
        raise HTTPException(500, f"Loading failed: {str(e)}")

    return _doc_dict(doc)


def load_and_parse_all(db, space_id, org_id):
    _find_space(db, space_id, org_id)
    docs = db.query(Document).filter(
        Document.rag_space_id == space_id,
        Document.status == DocStatus.UPLOADING,
    ).all()

    results = []
    for doc in docs:
        try:
            result = load_and_parse_document(db, space_id, doc.id, org_id)
            results.append({"id": doc.id, "file_name": doc.file_name, "status": result["status"]})
        except Exception as e:
            results.append({"id": doc.id, "file_name": doc.file_name, "status": "ERROR", "error": str(e)})

    return {"processed": len(results), "results": results}

# ══════════════════════════════════════════════════════
# UPLOAD FROM URL
# ══════════════════════════════════════════════════════

async def upload_from_url(db: Session, space_id: str, org_id: str, url: str) -> dict:
    space = _find_space(db, space_id, org_id)

    url = validate_url(url)
    filename = get_url_filename(url)

    doc = Document(
        file_name=filename,
        file_type="html",
        file_size=0,
        source_type="url",
        source_url=url,
        status=DocStatus.UPLOADING,
        rag_space_id=space_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        loaded_data = li_load_from_url(url)

        if not loaded_data or not loaded_data.get("raw_text"):
            raise Exception(f"No content found at {url}")

        upload_dir = os.path.join("uploads", space_id)
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{doc.id}.html")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(loaded_data["raw_text"])

        loaded_data["file_path"] = os.path.abspath(file_path)
        doc.loaded_content = json.dumps(loaded_data, ensure_ascii=False, default=str)
        doc.status = DocStatus.LOADED
        db.commit()
        db.refresh(doc)

    except Exception as e:
        doc.status = DocStatus.ERROR
        doc.error_msg = str(e)
        db.commit()
        raise HTTPException(500, f"Scraping failed: {str(e)}")

    return _doc_dict(doc)


# ══════════════════════════════════════════════════════
# GET LOADED CONTENT
# ══════════════════════════════════════════════════════

def get_loaded_content(db: Session, space_id: str, doc_id: str, org_id: str) -> dict:
    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    loaded_data = {}
    if doc.loaded_content:
        loaded_data = json.loads(doc.loaded_content)

    return {
        "document_id": doc.id,
        "file_name": doc.file_name,
        "status": doc.status,
        "raw_text": loaded_data.get("raw_text", ""),
        "num_pages": loaded_data.get("num_pages", 0),
        "file_type": loaded_data.get("file_type", ""),
        "category": loaded_data.get("category", ""),
        "metadata": loaded_data.get("metadata", {}),
        "total_chars": loaded_data.get("total_chars", 0),
    }


# ══════════════════════════════════════════════════════
# STEP 2: PARSE
# ══════════════════════════════════════════════════════

def parse_document(db: Session, space_id: str, doc_id: str, org_id: str) -> dict:
    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    if not doc.loaded_content:
        raise HTTPException(400, "No loaded content — upload the document first")

    try:
        loaded_data = json.loads(doc.loaded_content)

        parsed_doc = li_parse_document(loaded_data)

        if not parsed_doc.total_sections and not parsed_doc.total_tables:
            raise Exception("Parser produced no sections or tables")

        doc.extracted_content = parsed_doc.to_json()
        doc.status = DocStatus.EXTRACTED
        db.commit()
        db.refresh(doc)

    except Exception as e:
        doc.status = DocStatus.ERROR
        doc.error_msg = str(e)
        db.commit()
        raise HTTPException(500, f"Parsing failed: {str(e)}")

    return _doc_dict(doc)


def parse_all_documents(db: Session, space_id: str, org_id: str) -> dict:
    _find_space(db, space_id, org_id)
    docs = db.query(Document).filter(
        Document.rag_space_id == space_id,
        Document.status == DocStatus.LOADED,
    ).all()

    results = []
    for doc in docs:
        try:
            result = parse_document(db, space_id, doc.id, org_id)
            results.append({"id": doc.id, "file_name": doc.file_name, "status": "EXTRACTED"})
        except Exception as e:
            results.append({"id": doc.id, "file_name": doc.file_name, "status": "ERROR", "error": str(e)})

    return {"parsed": len(results), "results": results}


# ══════════════════════════════════════════════════════
# GET EXTRACTED CONTENT
# ══════════════════════════════════════════════════════

def get_extracted_content(db: Session, space_id: str, doc_id: str, org_id: str) -> dict:
    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    parsed_data = {}
    if doc.extracted_content:
        parsed_data = json.loads(doc.extracted_content)

    return {
        "document_id": doc.id,
        "file_name": doc.file_name,
        "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
        "parsed_document": parsed_data,
        "total_sections": parsed_data.get("total_sections", 0),
        "total_tables": parsed_data.get("total_tables", 0),
        "total_chars": parsed_data.get("total_chars", 0),
        "ocr_quality": parsed_data.get("ocr_quality", "unknown"),
        "ocr_issues": parsed_data.get("ocr_issues", []),
    }

def update_extracted_content(db: Session, space_id: str, doc_id: str, org_id: str, data) -> dict:
    from app.services.providers.parsers.parsed_document import ParsedDocument

    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    if not doc.extracted_content:
        raise HTTPException(400, "No parsed content to edit — parse the document first")

    existing = json.loads(doc.extracted_content)

    payload = data.dict(exclude_unset=True)
    if "title" in payload and payload["title"] is not None:
        existing["title"] = payload["title"]
    if "sections" in payload:
        existing["sections"] = payload["sections"]
    if "tables" in payload:
        existing["tables"] = payload["tables"]
    if "images" in payload:
        existing["images"] = payload["images"]
    if "metadata" in payload and payload["metadata"] is not None:
        existing["metadata"] = payload["metadata"]

    try:
        parsed_doc = ParsedDocument.from_dict(existing)
    except Exception as e:
        raise HTTPException(422, f"Invalid ParsedDocument structure: {str(e)}")

    doc.extracted_content = json.dumps(parsed_doc.to_dict(), ensure_ascii=False)
    doc.status = DocStatus.EXTRACTED
    db.commit()
    db.refresh(doc)

    return get_extracted_content(db, space_id, doc_id, org_id)

# ══════════════════════════════════════════════════════
# STEP 3: PROCESS — chunking + embedding
# ══════════════════════════════════════════════════════

def process_document(db: Session, space_id: str, doc_id: str, org_id: str) -> dict:
    space = _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    if not doc.extracted_content:
        raise HTTPException(400, "No parsed content — parse the document first")

    doc.status = DocStatus.PROCESSING
    db.commit()

    try:
        parsed_data = json.loads(doc.extracted_content)

        from app.services.providers.parsers.parsed_document import ParsedDocument
        parsed_doc = ParsedDocument.from_dict(parsed_data)
        content_blocks = parsed_doc.to_content_blocks()

        if not content_blocks:
            raise Exception("No content blocks from parsed document")

        db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
        db.flush()

        chunks = chunk_document(content_blocks, space, document=doc)
        if not chunks:
            raise Exception("No chunks generated")

        chunk_texts = [c["content"] for c in chunks]
        embeddings = embed_texts(chunk_texts)

        for i, chunk_data in enumerate(chunks):
            db_chunk = Chunk(
                content=chunk_data["content"],
                embedding=embeddings[i],
                page=chunk_data["page"],
                chunk_index=chunk_data["chunk_index"],
                document_id=doc.id,
                rag_space_id=space_id,
            )
            db.add(db_chunk)

        doc.num_chunks = len(chunks)
        doc.status = DocStatus.INDEXED
        db.commit()
        db.refresh(doc)

    except Exception as e:
        doc.status = DocStatus.ERROR
        doc.error_msg = str(e)
        db.commit()
        raise HTTPException(500, f"Processing failed: {str(e)}")

    return _doc_dict(doc)


def process_all_documents(db: Session, space_id: str, org_id: str) -> dict:
    space = _find_space(db, space_id, org_id)
    docs = db.query(Document).filter(
        Document.rag_space_id == space_id,
        Document.status == DocStatus.EXTRACTED,
    ).all()

    results = []
    for doc in docs:
        try:
            result = process_document(db, space_id, doc.id, org_id)
            results.append({"id": doc.id, "file_name": doc.file_name, "status": "INDEXED"})
        except Exception as e:
            results.append({"id": doc.id, "file_name": doc.file_name, "status": "ERROR", "error": str(e)})

    return {"processed": len(results), "results": results}


# ══════════════════════════════════════════════════════
# SEARCH (UNCHANGED)
# ══════════════════════════════════════════════════════

def pgvector_search(db, space_id, query_embedding, top_k):
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    sql = text("""
        SELECT id, content, page, document_id, chunk_index,
            1 - (embedding <=> :query_vec) AS similarity_score
        FROM chunks WHERE rag_space_id = :space_id AND embedding IS NOT NULL
        ORDER BY embedding <=> :query_vec LIMIT :top_k
    """)
    result = db.execute(sql, {"query_vec": embedding_str, "space_id": space_id, "top_k": top_k})
    return [{"content": r.content, "page": r.page, "document_id": r.document_id,
             "score": round(float(r.similarity_score), 4),
             "type": "table" if r.content.startswith("[TABLE]") else "text"} for r in result.fetchall()]


def keyword_score(query, content):
    query_words = set(query.lower().split())
    content_words = content.lower().split()
    content_counter = Counter(content_words)
    total = len(content_words) or 1
    score = sum(content_counter[w] / total for w in query_words if w in content_counter)
    return min(score * 10, 1.0)


def hybrid_search(db, space_id, query_text, query_embedding, top_k):
    candidates = pgvector_search(db, space_id, query_embedding, top_k * 2)
    if not candidates:
        return []
    for c in candidates:
        kw = keyword_score(query_text, c["content"])
        c["keyword_score"] = round(kw, 4)
        c["semantic_score"] = c["score"]
        combined = (0.7 * c["score"]) + (0.3 * kw)
        table_words = {"table", "tableau", "colonne", "ligne", "total", "montant", "chiffre", "données"}
        if c["content"].startswith("[TABLE]") and any(w in query_text.lower() for w in table_words):
            combined *= 1.15
        c["score"] = round(combined, 4)
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:top_k]


# ══════════════════════════════════════════════════════
# QUERY — now uses the LLM Factory (provider resolved per space)
# ══════════════════════════════════════════════════════

def query(db: Session, space_id: str, org_id: str, data: QueryRequest) -> dict:
    """Query the RAG space — hybrid search + configurable LLM (via factory)."""
    space = _find_space(db, space_id, org_id)

    query_embedding = embed_query(data.question)

    top_k = getattr(space, 'top_k', 5) or 5
    results = hybrid_search(db, space_id, data.question, query_embedding, top_k)

    if not results:
        return {"answer": "No relevant information found in the documents.", "sources": []}

    context_parts = []
    sources_info = []
    doc_cache = {}

    for i, r in enumerate(results):
        doc_id = r["document_id"]
        if doc_id not in doc_cache:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            doc_cache[doc_id] = doc.file_name if doc else "Unknown"

        doc_name = doc_cache[doc_id]
        context_parts.append(f"[Source {i+1}: {doc_name}, Page {r['page']}, Score: {r['score']}]\n{r['content']}")
        sources_info.append(f"Source {i+1}: {doc_name} (Page {r['page']}, Score: {r['score']})")

    context = "\n\n---\n\n".join(context_parts)
    sources_text = "\n".join(sources_info)

    # ── LLM Factory: resolves provider/model/key/prompt from the space ──
    answer = generate_answer(db, space, data.question, context, sources_text)

    sources = [
        {"content": r["content"][:200], "document": doc_cache.get(r["document_id"], "Unknown"),
         "page": r["page"], "score": r["score"]}
        for r in results
    ]

    return {"answer": answer, "sources": sources}