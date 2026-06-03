"""
RAG Service v5 — Professional Edition

SPLIT FLOW:
  1. upload_document()   → extract text ONLY → status: EXTRACTED
  2. IT reviews the extracted text in the frontend
  3. process_document()  → chunking + embedding → status: INDEXED

New endpoints:
  - get_extracted_content()  → returns raw extracted text for review
  - process_document()       → triggers chunking + embedding after review
  - process_all_documents()  → process all EXTRACTED docs in a space
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

# ── Processing factory ──
from app.services.providers.processing_factory import extract_document, extract_from_url, SUPPORTED_FORMATS

# ── Chunking factory ──
from app.services.providers.chunking_factory import chunk_document

# ── LangChain ──
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

# ── Embeddings ──
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
# UPLOAD — EXTRACT TEXT ONLY (no chunking)
# ══════════════════════════════════════════════════════

async def upload_document(db: Session, space_id: str, org_id: str, file: UploadFile) -> dict:
    """
    Step 1: Upload + extract text ONLY.
    Does NOT chunk or embed — IT reviews the extracted text first.
    Status: UPLOADING → EXTRACTED (or ERROR)
    """
    space = _find_space(db, space_id, org_id)

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED_FORMATS:
        supported = ", ".join(SUPPORTED_FORMATS.keys())
        raise HTTPException(400, f"Format '{ext}' not supported. Accepted: {supported}")

    content = await file.read()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    tmp.write(content)
    tmp.close()

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

    try:
        # Extract text ONLY — no chunking, no embedding
        content_blocks = extract_document(tmp.name)
        if not content_blocks:
            raise Exception("No content found in document")

        # Store raw extracted content as JSON
        doc.extracted_content = json.dumps(content_blocks, ensure_ascii=False)
        doc.status = DocStatus.EXTRACTED
        db.commit()
        db.refresh(doc)

    except Exception as e:
        doc.status = DocStatus.ERROR
        doc.error_msg = str(e)
        db.commit()
        raise HTTPException(500, f"Extraction failed: {str(e)}")
    finally:
        os.unlink(tmp.name)

    return _doc_dict(doc)


# ══════════════════════════════════════════════════════
# UPLOAD FROM URL — EXTRACT TEXT ONLY
# ══════════════════════════════════════════════════════

async def upload_from_url(db: Session, space_id: str, org_id: str, url: str) -> dict:
    """
    Upload from a URL — scrape and extract text.
    Status: UPLOADING → EXTRACTED (or ERROR)
    """
    space = _find_space(db, space_id, org_id)

    from app.services.providers.processing_factory import validate_url, get_url_filename
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
        content_blocks = extract_from_url(url)
        if not content_blocks:
            raise Exception(f"No content found at {url}")

        doc.extracted_content = json.dumps(content_blocks, ensure_ascii=False)
        doc.status = DocStatus.EXTRACTED
        db.commit()
        db.refresh(doc)

    except Exception as e:
        doc.status = DocStatus.ERROR
        doc.error_msg = str(e)
        db.commit()
        raise HTTPException(500, f"Scraping failed: {str(e)}")

    return _doc_dict(doc)


# ══════════════════════════════════════════════════════
# GET EXTRACTED CONTENT — for IT review
# ══════════════════════════════════════════════════════

def get_extracted_content(db: Session, space_id: str, doc_id: str, org_id: str) -> dict:
    """Returns the raw extracted text for IT to review before processing."""
    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    blocks = []
    if doc.extracted_content:
        blocks = json.loads(doc.extracted_content)

    return {
        "document_id": doc.id,
        "file_name": doc.file_name,
        "status": doc.status,
        "blocks": blocks,
        "total_blocks": len(blocks),
        "text_blocks": len([b for b in blocks if b.get("type") == "text"]),
        "table_blocks": len([b for b in blocks if b.get("type") == "table"]),
        "total_chars": sum(len(b.get("content", "")) for b in blocks),
    }


# ══════════════════════════════════════════════════════
# PROCESS DOCUMENT — chunking + embedding (after review)
# ══════════════════════════════════════════════════════

def process_document(db: Session, space_id: str, doc_id: str, org_id: str) -> dict:
    """
    Step 2: After IT reviews the extracted text, process it.
    Chunking + embedding → store in pgvector.
    Status: EXTRACTED → PROCESSING → INDEXED (or ERROR)
    """
    space = _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    if not doc.extracted_content:
        raise HTTPException(400, "No extracted content — upload and extract first")

    doc.status = DocStatus.PROCESSING
    db.commit()

    try:
        content_blocks = json.loads(doc.extracted_content)

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

    return {
        "processed": len(results),
        "results": results,
    }


# ══════════════════════════════════════════════════════
# SEARCH + LLM (unchanged)
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
Use **bold** for important terms. Use bullet points for lists.
If the answer is not in the context, say: "This information is not available in the uploaded documents."
Never invent facts. Answer in the SAME LANGUAGE as the question.
If the context contains [TABLE] markers, read the table carefully and present data clearly.

CONTEXT:
{context}

SOURCES:
{sources_info}"""
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=question)]
    return llm.invoke(messages).content


# ══════════════════════════════════════════════════════
# RAG SPACE CRUD
# ══════════════════════════════════════════════════════

def create_space(db, data, org_id, current_user=None):
    from app.models.department import Department
    if data.department_id:
        dept = db.query(Department).filter(Department.id == data.department_id, Department.organization_id == org_id).first()
        if not dept:
            raise HTTPException(404, "Department not found")
        if current_user and current_user.role == "IT":
            if data.department_id not in [d.id for d in current_user.departments]:
                raise HTTPException(403, "You don't have access to this department")
    space = RAGSpace(
        name=data.name, description=data.description, organization_id=org_id, department_id=data.department_id,
        chunk_size=data.chunk_size, chunk_overlap=data.chunk_overlap, chunk_strategy=data.chunk_strategy,
        embedding_provider=data.embedding_provider, embedding_model=data.embedding_model,
        llm_provider=data.llm_provider, llm_model=data.llm_model,
        llm_temperature=data.llm_temperature, llm_max_tokens=data.llm_max_tokens,
        top_k=data.top_k, search_engine=data.search_engine,
        semantic_weight=data.semantic_weight, reranking_enabled=data.reranking_enabled,
        system_prompt=data.system_prompt,
    )
    db.add(space)
    db.commit()
    db.refresh(space)
    return _space_dict(space, db)


def list_spaces(db, org_id, current_user=None):
    if current_user and current_user.role == "ADMIN":
        spaces = db.query(RAGSpace).filter(RAGSpace.organization_id == org_id).all()
    elif current_user:
        dept_ids = [d.id for d in current_user.departments]
        if not dept_ids:
            return []
        spaces = db.query(RAGSpace).filter(RAGSpace.organization_id == org_id, RAGSpace.department_id.in_(dept_ids)).all()
    else:
        spaces = db.query(RAGSpace).filter(RAGSpace.organization_id == org_id).all()
    return [_space_dict(s, db) for s in spaces]

def get_space(db, space_id, org_id):
    return _space_dict(_find_space(db, space_id, org_id), db)

def update_space(db, space_id, org_id, data):
    space = _find_space(db, space_id, org_id)
    for key, value in data.dict(exclude_none=True).items():
        setattr(space, key, value)
    db.commit()
    db.refresh(space)
    return _space_dict(space, db)

def delete_space(db, space_id, org_id):
    space = _find_space(db, space_id, org_id)
    db.delete(space)
    db.commit()
    return {"message": f"RAG space '{space.name}' deleted"}


# ══════════════════════════════════════════════════════
# DOCUMENTS
# ══════════════════════════════════════════════════════

def list_documents(db, space_id, org_id):
    _find_space(db, space_id, org_id)
    docs = db.query(Document).filter(Document.rag_space_id == space_id).all()
    return [_doc_dict(d) for d in docs]

def delete_document(db, space_id, doc_id, org_id):
    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    db.delete(doc)
    db.commit()
    return {"message": f"Document '{doc.file_name}' deleted"}

def list_chunks(db, space_id, doc_id, org_id):
    _find_space(db, space_id, org_id)
    chunks = db.query(Chunk).filter(Chunk.document_id == doc_id, Chunk.rag_space_id == space_id).order_by(Chunk.chunk_index).all()
    return [{"id": c.id, "content": c.content, "page": c.page, "chunk_index": c.chunk_index,
             "type": "table" if c.content.startswith("[TABLE]") else "text", "char_count": len(c.content)} for c in chunks]


# ══════════════════════════════════════════════════════
# QUERY
# ══════════════════════════════════════════════════════

def query(db, space_id, org_id, data):
    space = _find_space(db, space_id, org_id)
    query_embedding = embed_query(data.question)
    results = hybrid_search(db, space_id, data.question, query_embedding, space.top_k)
    if not results:
        return {"answer": "No documents available to answer this question. Please upload and process documents first.", "sources": []}
    doc_ids = list(set(r["document_id"] for r in results))
    docs = db.query(Document).filter(Document.id.in_(doc_ids)).all()
    doc_names = {d.id: d.file_name for d in docs}
    context_parts, sources, sources_info_parts = [], [], []
    for i, r in enumerate(results):
        doc_name = doc_names.get(r["document_id"], "unknown")
        marker = f"[Source {i+1}: {doc_name}, page {r['page']}, relevance: {r['score']}]"
        sources_info_parts.append(marker)
        context_parts.append(f"{marker}\n{r['content']}")
        sources.append({"content": r["content"][:300], "document": doc_name, "page": r["page"],
                        "score": r["score"], "type": r["type"]})
    context = "\n\n===\n\n".join(context_parts)
    answer = generate_answer(data.question, context, "\n".join(sources_info_parts))
    return {"answer": answer, "sources": sources}


# ══════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════

def _find_space(db, space_id, org_id):
    space = db.query(RAGSpace).filter(RAGSpace.id == space_id, RAGSpace.organization_id == org_id).first()
    if not space:
        raise HTTPException(404, "RAG space not found")
    return space

def _space_dict(space, db=None):
    from app.models.department import Department
    num_docs = num_chunks = 0
    dept_name = None
    if db:
        num_docs = db.query(Document).filter(Document.rag_space_id == space.id).count()
        num_chunks = db.query(Chunk).filter(Chunk.rag_space_id == space.id).count()
        if space.department_id:
            dept = db.query(Department).filter(Department.id == space.department_id).first()
            dept_name = dept.name if dept else None
    return {
        "id": space.id, "name": space.name, "description": space.description,
        "status": getattr(space, 'status', 'DRAFT') or 'DRAFT',
        "organization_id": space.organization_id,
        "department_id": space.department_id, "department_name": dept_name,
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
    return {
        "id": doc.id, "file_name": doc.file_name, "file_type": doc.file_type,
        "file_size": doc.file_size, "source_type": getattr(doc, 'source_type', 'local') or 'local',
        "source_url": getattr(doc, 'source_url', None),
        "num_chunks": doc.num_chunks, "status": doc.status, "error_msg": doc.error_msg,
        "has_extracted_content": bool(doc.extracted_content) if hasattr(doc, 'extracted_content') else False,
        "rag_space_id": doc.rag_space_id, "uploaded_at": str(doc.uploaded_at),
    }
