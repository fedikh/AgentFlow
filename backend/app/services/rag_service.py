"""
RAG Service v6 — LlamaIndex Loaders & Parsers Edition

THREE-STEP FLOW:
  1. upload_document()    → LlamaIndex LOADER → raw text → status: LOADED
  2. parse_document()     → LlamaIndex PARSER → structured blocks → status: EXTRACTED
  3. process_document()   → chunking + embedding → status: INDEXED

New:
  - get_loaded_content()   → returns raw loaded text for review
  - parse_document()       → triggers LlamaIndex parsing after loader review
  - get_extracted_content() → returns parsed/structured blocks for review

KEPT UNCHANGED:
  - process_document()     → chunking + embedding (same as before)
  - query()               → hybrid search + Groq LLM (same as before)
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

# ── Modular Loaders & Parsers (replaces processing_factory) ──
from app.services.providers.loaders import (
    load_document as li_load_document,
    load_from_url as li_load_from_url,
    SUPPORTED_FORMATS,
)
from app.services.providers.loaders._utils import validate_url, get_url_filename
from app.services.providers.parsers import parse_document as li_parse_document

# ── Chunking factory (UNCHANGED) ──
from app.services.providers.chunking_factory import chunk_document

# ── LangChain (UNCHANGED) ──
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

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
        "embedding_provider": getattr(space, 'embedding_provider', 'LOCAL') or 'LOCAL',
        "embedding_model": getattr(space, 'embedding_model', 'BAAI/bge-m3') or 'BAAI/bge-m3',
        "llm_provider": getattr(space, 'llm_provider', 'GROQ') or 'GROQ',
        "llm_model": getattr(space, 'llm_model', 'llama-3.3-70b-versatile') or 'llama-3.3-70b-versatile',
        "llm_temperature": getattr(space, 'llm_temperature', 0.2) if getattr(space, 'llm_temperature', None) is not None else 0.2,
        "llm_max_tokens": getattr(space, 'llm_max_tokens', 1024) or 1024,
        "top_k": space.top_k,
        "search_engine": getattr(space, 'search_engine', 'HYBRID') or 'HYBRID',
        "semantic_weight": getattr(space, 'semantic_weight', 0.7) if getattr(space, 'semantic_weight', None) is not None else 0.7,
        "reranking_enabled": getattr(space, 'reranking_enabled', False) or False,
        "system_prompt": getattr(space, 'system_prompt', None),
        "num_documents": num_docs, "num_chunks": num_chunks,
        "created_at": str(space.created_at),
    }

def _doc_dict(doc):
    # Force status to plain string (enum can serialize as "DocStatus.LOADED" otherwise)
    status = doc.status.value if hasattr(doc.status, 'value') else str(doc.status)
    return {
        "id": doc.id, "file_name": doc.file_name, "file_type": doc.file_type,
        "file_size": doc.file_size,
        "source_type": getattr(doc, 'source_type', 'local') or 'local',
        "source_url": getattr(doc, 'source_url', None),
        "num_chunks": doc.num_chunks, "status": status, "error_msg": doc.error_msg,
        "has_loaded_content": bool(doc.loaded_content) if hasattr(doc, 'loaded_content') else False,
        "has_extracted_content": bool(doc.extracted_content) if hasattr(doc, 'extracted_content') else False,
        "rag_space_id": doc.rag_space_id, "uploaded_at": str(doc.uploaded_at),
    }


# ══════════════════════════════════════════════════════
# SPACES CRUD (UNCHANGED)
# ══════════════════════════════════════════════════════

def create_space(db: Session, data: CreateRAGSpaceRequest, org_id: str, user) -> dict:
    space = RAGSpace(
        name=data.name, description=data.description or "",
        organization_id=org_id, department_id=data.department_id,
        chunk_size=data.chunk_size or 512, chunk_overlap=data.chunk_overlap or 50,
        chunk_strategy=data.chunk_strategy or "FIXED",
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
    for field, value in data.dict(exclude_unset=True).items():
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

    # Delete saved file if it exists
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
# STEP 1: UPLOAD → LLAMAINDEX LOADER (raw text)
# ══════════════════════════════════════════════════════

async def upload_document(db: Session, space_id: str, org_id: str, file: UploadFile) -> dict:
    """
    Step 1: Upload + LOAD raw text.
    File is saved permanently so Unstructured can read it during parsing.
    Status: UPLOADING → LOADED (or ERROR)
    """
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

    # Save file permanently (Unstructured needs the file for parsing)
    upload_dir = os.path.join("uploads", space_id)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{doc.id}{ext}")

    with open(file_path, "wb") as f:
        f.write(content)

    try:
        # ── LOADER → raw text ──
        loaded_data = li_load_document(file_path)
        from app.services.providers.cleaners import clean_loaded_data
        loaded_data = clean_loaded_data(loaded_data)

        if not loaded_data or not loaded_data.get("raw_text"):
            raise Exception("No content found in document")

        # Store file_path so the parser can find the file
        loaded_data["file_path"] = os.path.abspath(file_path)

        # Check if loader already produced ParsedDocument (PDF/DOCX via Docling)
        parsed_doc_data = loaded_data.pop("parsed_document", None)

        doc.loaded_content = json.dumps(loaded_data, ensure_ascii=False, default=str)

        if parsed_doc_data:
            # Docling did both loading + parsing — skip Parse step
            doc.extracted_content = json.dumps(parsed_doc_data, ensure_ascii=False)
            doc.status = DocStatus.EXTRACTED
        else:
            # Other formats — user clicks Parse later
            doc.status = DocStatus.LOADED

        db.commit()
        db.refresh(doc)

    except Exception as e:
        doc.status = DocStatus.ERROR
        doc.error_msg = str(e)
        db.commit()
        # Clean up file on error
        if os.path.exists(file_path):
            os.unlink(file_path)
        raise HTTPException(500, f"Loading failed: {str(e)}")

    return _doc_dict(doc)


# ══════════════════════════════════════════════════════
# UPLOAD FROM URL → LLAMAINDEX LOADER
# ══════════════════════════════════════════════════════

async def upload_from_url(db: Session, space_id: str, org_id: str, url: str) -> dict:
    """
    Upload from a URL — scrape and save HTML for Unstructured parsing.
    Status: UPLOADING → LOADED (or ERROR)
    """
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

        # Save scraped content to file for Unstructured parsing
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
# GET LOADED CONTENT — raw text for IT review
# ══════════════════════════════════════════════════════

def get_loaded_content(db: Session, space_id: str, doc_id: str, org_id: str) -> dict:
    """Returns the raw loaded text (from LlamaIndex loader) for IT to review."""
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
# STEP 2: PARSE — LlamaIndex parser → structured blocks
# ══════════════════════════════════════════════════════

def parse_document(db: Session, space_id: str, doc_id: str, org_id: str) -> dict:
    """
    Step 2: Parse loaded text into ParsedDocument.
    Status: LOADED → EXTRACTED (or ERROR)
    """
    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    if not doc.loaded_content:
        raise HTTPException(400, "No loaded content — upload the document first")

    try:
        loaded_data = json.loads(doc.loaded_content)

        # ── Parser produces ParsedDocument ──
        parsed_doc = li_parse_document(loaded_data)

        if not parsed_doc.total_sections and not parsed_doc.total_tables:
            raise Exception("Parser produced no sections or tables")

        # Store ParsedDocument as JSON
        doc.extracted_content = parsed_doc.to_json()
        doc.status = DocStatus.EXTRACTED
        db.commit()
        db.refresh(doc)

    except Exception as e:
        doc.status = DocStatus.ERROR
        doc.error_msg = str(e)
        db.commit()
        raise HTTPException(500, f"Parsing failed: {str(e)}")

    except Exception as e:
        doc.status = DocStatus.ERROR
        doc.error_msg = str(e)
        db.commit()
        raise HTTPException(500, f"Parsing failed: {str(e)}")

    return _doc_dict(doc)


def parse_all_documents(db: Session, space_id: str, org_id: str) -> dict:
    """Parse ALL documents with status LOADED in this space."""
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
# GET EXTRACTED (PARSED) CONTENT — for IT review
# ══════════════════════════════════════════════════════

def get_extracted_content(db: Session, space_id: str, doc_id: str, org_id: str) -> dict:
    """Returns the ParsedDocument for IT to review."""
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


# ══════════════════════════════════════════════════════
# STEP 3: PROCESS — chunking + embedding (UNCHANGED)
# ══════════════════════════════════════════════════════

def process_document(db: Session, space_id: str, doc_id: str, org_id: str) -> dict:
    """
    Step 3: After IT reviews the parsed blocks, process them.
    Chunking + embedding → store in pgvector.
    Status: EXTRACTED → PROCESSING → INDEXED (or ERROR)
    """
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

        # Convert ParsedDocument → content_blocks for the Chunking Engine
        from app.services.providers.parsers.parsed_document import ParsedDocument
        parsed_doc = ParsedDocument.from_dict(parsed_data)
        content_blocks = parsed_doc.to_content_blocks()

        if not content_blocks:
            raise Exception("No content blocks from parsed document")

        # Delete old chunks if re-processing
        db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
        db.flush()

        # Step 1: Chunk using the space's strategy
        chunks = chunk_document(content_blocks, space)
        if not chunks:
            raise Exception("No chunks generated")

        # Step 2: Embed
        chunk_texts = [c["content"] for c in chunks]
        embeddings = embed_texts(chunk_texts)

        # Step 3: Store in pgvector
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
    """Process ALL documents with status EXTRACTED in this space."""
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
# SEARCH + LLM (COMPLETELY UNCHANGED)
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


def generate_answer(question, context, sources_info):
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.2, groq_api_key=settings.GROQ_API_KEY)
    system_prompt = f"""You are a professional AI assistant for an enterprise organization.
Answer questions using ONLY the provided context. Format your answers clearly.
Use **bold** for important terms.
If the context doesn't contain relevant information, say so clearly.
Always cite your sources at the end.

CONTEXT:
{context}

SOURCES AVAILABLE:
{sources_info}"""

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=question)]
    response = llm.invoke(messages)
    return response.content


def query(db: Session, space_id: str, org_id: str, data: QueryRequest) -> dict:
    """Query the RAG space — hybrid search + Groq LLM (UNCHANGED)."""
    space = _find_space(db, space_id, org_id)

    query_embedding = embed_query(data.question)

    top_k = getattr(space, 'top_k', 5) or 5
    results = hybrid_search(db, space_id, data.question, query_embedding, top_k)

    if not results:
        return {"answer": "No relevant information found in the documents.", "sources": []}

    # Build context
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

    answer = generate_answer(data.question, context, sources_text)

    sources = [
        {"content": r["content"][:200], "document": doc_cache.get(r["document_id"], "Unknown"),
         "page": r["page"], "score": r["score"]}
        for r in results
    ]

    return {"answer": answer, "sources": sources}