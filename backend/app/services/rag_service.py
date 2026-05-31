"""
RAG Service v4 — Multi-Format Edition

Pipeline:
1. Upload PDF/DOCX/TXT/CSV/XLSX → extract text + tables
2. Smart chunking — tables stay intact
3. sentence-transformers generates embeddings (free, local)
4. Store chunks + embeddings in PostgreSQL with pgvector
5. Query: embed question → pgvector SQL cosine search → top K
6. Hybrid: pgvector (semantic) + keyword scoring
7. LLM generates answer from context
"""

import os
import re
import math
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

# ── Multi-format document processor ──
from app.services.providers.processing_factory import extract_document, SUPPORTED_FORMATS
from app.services.providers.chunking_factory import chunk_document

# ── LangChain ──
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage


# ── Embeddings (free, local, lazy loaded) ──
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
                print("Loading BGE-base fallback...")
                _embed_model = SentenceTransformer("BAAI/bge-base-en-v1.5")
                print("✅ BGE-base loaded (768 dims)")
            except Exception as e2:
                print(f"⚠️ BGE-base failed: {e2}")
                print("Loading all-MiniLM-L6-v2 fallback...")
                _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
                print("✅ all-MiniLM loaded (384 dims)")
    return _embed_model


# ══════════════════════════════════════════════════════
# STEP 2: SMART CHUNKING
# ══════════════════════════════════════════════════════

def smart_chunk(content_blocks: list[dict], chunk_size: int = 512, chunk_overlap: int = 50) -> list[dict]:
    chunks = []
    idx = 0

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    for block in content_blocks:
        if block["type"] == "table":
            chunks.append({
                "content": f"[TABLE]\n{block['content']}",
                "page": block["page"],
                "chunk_index": idx,
                "type": "table",
            })
            idx += 1
        elif block["type"] == "text":
            text_content = block["content"]
            current_title = ""
            for line in text_content.split("\n"):
                stripped = line.strip()
                if stripped and len(stripped) < 80 and (stripped.isupper() or stripped.endswith(":")):
                    current_title = stripped

            if len(text_content) <= chunk_size:
                content = f"[Section: {current_title}]\n{text_content}" if current_title else text_content
                chunks.append({"content": content, "page": block["page"], "chunk_index": idx, "type": "text"})
                idx += 1
            else:
                from langchain.schema import Document as LCDoc
                lc_docs = splitter.split_documents([LCDoc(page_content=text_content)])
                for doc in lc_docs:
                    content = doc.page_content
                    if current_title and current_title not in content:
                        content = f"[Section: {current_title}]\n{content}"
                    chunks.append({"content": content, "page": block["page"], "chunk_index": idx, "type": "text"})
                    idx += 1

    return chunks


# ══════════════════════════════════════════════════════
# STEP 3: EMBEDDINGS (free, local)
# ══════════════════════════════════════════════════════

def embed_texts(texts: list[str]) -> list[list[float]]:
    model = _get_embed_model()
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return [e.tolist() for e in embeddings]

def embed_query(text: str) -> list[float]:
    model = _get_embed_model()
    embedding = model.encode("Represent this sentence: " + text, show_progress_bar=False, normalize_embeddings=True)
    return embedding.tolist()


# ══════════════════════════════════════════════════════
# STEP 4: PGVECTOR SEARCH
# ══════════════════════════════════════════════════════

def pgvector_search(db: Session, space_id: str, query_embedding: list[float], top_k: int) -> list[dict]:
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    sql = text("""
        SELECT 
            id, content, page, document_id, chunk_index,
            1 - (embedding <=> :query_vec) AS similarity_score
        FROM chunks
        WHERE rag_space_id = :space_id
        AND embedding IS NOT NULL
        ORDER BY embedding <=> :query_vec
        LIMIT :top_k
    """)

    result = db.execute(sql, {
        "query_vec": embedding_str,
        "space_id": space_id,
        "top_k": top_k,
    })

    rows = result.fetchall()
    return [
        {
            "content": row.content,
            "page": row.page,
            "document_id": row.document_id,
            "score": round(float(row.similarity_score), 4),
            "type": "table" if row.content.startswith("[TABLE]") else "text",
        }
        for row in rows
    ]


def keyword_score(query: str, content: str) -> float:
    query_words = set(query.lower().split())
    content_words = content.lower().split()
    content_counter = Counter(content_words)
    total = len(content_words) or 1

    score = 0.0
    for word in query_words:
        if word in content_counter:
            tf = content_counter[word] / total
            score += tf

    return min(score * 10, 1.0)


def hybrid_search(db: Session, space_id: str, query_text: str, query_embedding: list[float], top_k: int) -> list[dict]:
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
# STEP 5: LLM GENERATION
# ══════════════════════════════════════════════════════

def generate_answer(question: str, context: str, sources_info: str) -> str:
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.2,
        groq_api_key=settings.GROQ_API_KEY,
    )

    system_prompt = f"""You are a professional AI assistant for an enterprise organization.
Answer questions using ONLY the provided context. Format your answers clearly.

RESPONSE FORMAT RULES:
- Use **bold** for important terms, names, and key values.
- Use bullet points (•) for lists of items.
- Use numbered lists (1. 2. 3.) for steps or ordered items.
- Use headings with ## for sections when the answer covers multiple topics.
- When presenting numbers, dates, or amounts, put them in **bold**.
- Keep paragraphs short — max 2-3 sentences each.
- Add a blank line between sections for readability.
- End with a "📄 Sources:" section listing where the information comes from.

ACCURACY RULES:
- Use ONLY information from the CONTEXT below.
- If the answer is not in the context, say: "❌ This information is not available in the uploaded documents."
- Never invent facts, numbers, dates, or names.
- Answer in the SAME LANGUAGE as the question.

HANDLING TABLES:
- If the context contains [TABLE] markers, read the table carefully.
- Present table data in a clean formatted way:
  • Use bullet points for small tables (< 5 rows)
  • Recreate the table in markdown format for larger tables
- Always mention the column names when citing table values.

CONTEXT:
{context}

SOURCES AVAILABLE:
{sources_info}"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=question),
    ]

    response = llm.invoke(messages)
    return response.content


# ══════════════════════════════════════════════════════
# RAG SPACE CRUD
# ══════════════════════════════════════════════════════

def create_space(db, data, org_id, current_user=None):
    from app.models.department import Department
    from app.models.rag_space import RAGSpace

    if data.department_id:
        dept = db.query(Department).filter(
            Department.id == data.department_id,
            Department.organization_id == org_id,
        ).first()
        if not dept:
            raise HTTPException(404, "Department not found")

        if current_user and current_user.role == "IT":
            user_dept_ids = [d.id for d in current_user.departments]
            if data.department_id not in user_dept_ids:
                raise HTTPException(403, "You don't have access to this department")

    space = RAGSpace(
        name=data.name,
        description=data.description,
        organization_id=org_id,
        department_id=data.department_id,
        chunk_size=data.chunk_size,
        chunk_overlap=data.chunk_overlap,
        chunk_strategy=data.chunk_strategy,
        embedding_provider=data.embedding_provider,
        embedding_model=data.embedding_model,
        llm_provider=data.llm_provider,
        llm_model=data.llm_model,
        llm_temperature=data.llm_temperature,
        llm_max_tokens=data.llm_max_tokens,
        top_k=data.top_k,
        search_engine=data.search_engine,
        semantic_weight=data.semantic_weight,
        reranking_enabled=data.reranking_enabled,
        system_prompt=data.system_prompt,
    )
    db.add(space)
    db.commit()
    db.refresh(space)
    return _space_dict(space, db)


def list_spaces(db: Session, org_id: str, current_user=None) -> list[dict]:
    if current_user and current_user.role == "ADMIN":
        spaces = db.query(RAGSpace).filter(RAGSpace.organization_id == org_id).all()
    elif current_user:
        dept_ids = [d.id for d in current_user.departments]
        if not dept_ids:
            return []
        spaces = db.query(RAGSpace).filter(
            RAGSpace.organization_id == org_id,
            RAGSpace.department_id.in_(dept_ids),
        ).all()
    else:
        spaces = db.query(RAGSpace).filter(RAGSpace.organization_id == org_id).all()

    return [_space_dict(s, db) for s in spaces]

def get_space(db: Session, space_id: str, org_id: str) -> dict:
    return _space_dict(_find_space(db, space_id, org_id), db)

def update_space(db: Session, space_id: str, org_id: str, data: UpdateRAGSpaceRequest) -> dict:
    space = _find_space(db, space_id, org_id)
    for key, value in data.dict(exclude_none=True).items():
        setattr(space, key, value)
    db.commit()
    db.refresh(space)
    return _space_dict(space, db)

def delete_space(db: Session, space_id: str, org_id: str) -> dict:
    space = _find_space(db, space_id, org_id)
    db.delete(space)
    db.commit()
    return {"message": f"RAG space '{space.name}' deleted"}


# ══════════════════════════════════════════════════════
# UPLOAD — FULL PIPELINE (MULTI-FORMAT)
# ══════════════════════════════════════════════════════

async def upload_document(db: Session, space_id: str, org_id: str, file: UploadFile) -> dict:
    """
    1. Save file → temp
    2. Extract text + tables (PDF, DOCX, TXT, CSV, XLSX)
    3. Smart chunking
    4. sentence-transformers embeds chunks
    5. Store in PostgreSQL with pgvector
    """
    space = _find_space(db, space_id, org_id)

    # ── CHANGED: multi-format validation ──
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED_FORMATS:
        supported = ", ".join(SUPPORTED_FORMATS.keys())
        raise HTTPException(400, f"Format '{ext}' not supported. Accepted: {supported}")

    content = await file.read()

    # ── CHANGED: use actual extension for temp file ──
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    tmp.write(content)
    tmp.close()

    # ── CHANGED: detect file type from extension ──
    doc = Document(
        file_name=file.filename,
        file_type=ext.replace(".", ""),
        file_size=len(content),
        status=DocStatus.INDEXING,
        rag_space_id=space_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        # Step 1: Extract (multi-format)
        # ── CHANGED: use document_processors factory instead of extract_pdf_content ──
        content_blocks = extract_document(tmp.name)
        if not content_blocks:
            raise Exception("No content found in document")

        # Step 2: Chunk
        chunks = chunk_document(content_blocks, space)
        if not chunks:
            raise Exception("No chunks generated")

        # Step 3: Embed
        chunk_texts = [c["content"] for c in chunks]
        embeddings = embed_texts(chunk_texts)

        # Step 4: Store with pgvector
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
        raise HTTPException(500, f"Indexing failed: {str(e)}")
    finally:
        os.unlink(tmp.name)

    return _doc_dict(doc)


# ══════════════════════════════════════════════════════
# DOCUMENTS
# ══════════════════════════════════════════════════════

def list_documents(db: Session, space_id: str, org_id: str) -> list[dict]:
    _find_space(db, space_id, org_id)
    docs = db.query(Document).filter(Document.rag_space_id == space_id).all()
    return [_doc_dict(d) for d in docs]


def list_chunks(db, space_id, doc_id, org_id):
    _find_space(db, space_id, org_id)
    from app.models.chunk import Chunk
    chunks = db.query(Chunk).filter(
        Chunk.document_id == doc_id,
        Chunk.rag_space_id == space_id,
    ).order_by(Chunk.chunk_index).all()
    return [
        {"id": c.id, "content": c.content, "page": c.page,
         "chunk_index": c.chunk_index,
         "type": "table" if c.content.startswith("[TABLE]") else "text",
         "char_count": len(c.content)}
        for c in chunks
    ]

def delete_document(db: Session, space_id: str, doc_id: str, org_id: str) -> dict:
    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    db.delete(doc)
    db.commit()
    return {"message": f"Document '{doc.file_name}' deleted"}


# ══════════════════════════════════════════════════════
# QUERY — FULL RAG PIPELINE
# ══════════════════════════════════════════════════════

def query(db: Session, space_id: str, org_id: str, data: QueryRequest) -> dict:
    space = _find_space(db, space_id, org_id)

    query_embedding = embed_query(data.question)

    results = hybrid_search(db, space_id, data.question, query_embedding, space.top_k)

    if not results:
        return {
            "answer": "I don't have any documents to answer this question. Please upload documents first.",
            "sources": [],
        }

    doc_ids = list(set(r["document_id"] for r in results))
    docs = db.query(Document).filter(Document.id.in_(doc_ids)).all()
    doc_names = {d.id: d.file_name for d in docs}

    context_parts = []
    sources = []
    sources_info_parts = []

    for i, r in enumerate(results):
        doc_name = doc_names.get(r["document_id"], "unknown")
        marker = f"[Source {i+1}: {doc_name}, page {r['page']}, relevance: {r['score']}]"
        sources_info_parts.append(marker)
        context_parts.append(f"{marker}\n{r['content']}")

        sources.append({
            "content": r["content"][:300] + "..." if len(r["content"]) > 300 else r["content"],
            "document": doc_name,
            "page": r["page"],
            "score": r["score"],
            "type": r["type"],
            "semantic_score": r.get("semantic_score", 0),
            "keyword_score": r.get("keyword_score", 0),
        })

    context = "\n\n========================================\n\n".join(context_parts)
    sources_info = "\n".join(sources_info_parts)

    answer = generate_answer(data.question, context, sources_info)

    return {"answer": answer, "sources": sources}


# ══════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════

def _find_space(db: Session, space_id: str, org_id: str) -> RAGSpace:
    space = db.query(RAGSpace).filter(
        RAGSpace.id == space_id, RAGSpace.organization_id == org_id
    ).first()
    if not space:
        raise HTTPException(404, "RAG space not found")
    return space


def _space_dict(space, db=None):
    from app.models.department import Department

    num_docs = 0
    num_chunks = 0
    dept_name = None

    if db:
        num_docs = db.query(Document).filter(Document.rag_space_id == space.id).count()
        num_chunks = db.query(Chunk).filter(Chunk.rag_space_id == space.id).count()
        if space.department_id:
            dept = db.query(Department).filter(Department.id == space.department_id).first()
            dept_name = dept.name if dept else None

    return {
        "id":                space.id,
        "name":              space.name,
        "description":       space.description,
        "status":            space.status if hasattr(space, 'status') and space.status else "DRAFT",
        "organization_id":   space.organization_id,
        "department_id":     space.department_id,
        "department_name":   dept_name,
        "chunk_size":        space.chunk_size,
        "chunk_overlap":     space.chunk_overlap,
        "chunk_strategy":    space.chunk_strategy,
        "embedding_provider": space.embedding_provider if hasattr(space, 'embedding_provider') and space.embedding_provider else "LOCAL",
        "embedding_model":    space.embedding_model if hasattr(space, 'embedding_model') and space.embedding_model else "BAAI/bge-m3",
        "llm_provider":      space.llm_provider if hasattr(space, 'llm_provider') and space.llm_provider else "GROQ",
        "llm_model":         space.llm_model if hasattr(space, 'llm_model') and space.llm_model else "llama-3.3-70b-versatile",
        "llm_temperature":   space.llm_temperature if hasattr(space, 'llm_temperature') and space.llm_temperature is not None else 0.2,
        "llm_max_tokens":    space.llm_max_tokens if hasattr(space, 'llm_max_tokens') and space.llm_max_tokens else 1024,
        "top_k":             space.top_k,
        "search_engine":     space.search_engine if hasattr(space, 'search_engine') and space.search_engine else "HYBRID",
        "semantic_weight":   space.semantic_weight if hasattr(space, 'semantic_weight') and space.semantic_weight is not None else 0.7,
        "reranking_enabled": space.reranking_enabled if hasattr(space, 'reranking_enabled') and space.reranking_enabled is not None else False,
        "system_prompt":     space.system_prompt if hasattr(space, 'system_prompt') else None,
        "num_documents":     num_docs,
        "num_chunks":        num_chunks,
        "created_at":        str(space.created_at),
    }


def _doc_dict(doc: Document) -> dict:
    return {
        "id": doc.id, "file_name": doc.file_name, "file_type": doc.file_type,
        "file_size": doc.file_size, "num_chunks": doc.num_chunks,
        "status": doc.status, "error_msg": doc.error_msg,
        "rag_space_id": doc.rag_space_id, "uploaded_at": str(doc.uploaded_at),
    }