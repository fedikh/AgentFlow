"""
RAG Service v3 — pgvector Edition

Pipeline:
1. Upload PDF → pdfplumber extracts text + tables
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

# ── LangChain ──
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage, SystemMessage

# ── Embeddings (free, local, lazy loaded) ──
_embed_model = None

def _get_embed_model():
    """
    Lazy load the embedding model.
    Tries 3 models in order — uses whichever works.
    Only loads once, then cached in memory.
    """
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
# STEP 1: EXTRACT TEXT + TABLES FROM PDF
# ══════════════════════════════════════════════════════

def extract_pdf_content(file_path: str) -> list[dict]:
    """
    Extract text AND tables from PDF using pdfplumber.
    
    3 methods tried on each page:
    1. pdfplumber standard table detection (visible borders)
    2. pdfplumber text-based detection (borderless tables)
    3. Line-based detection (columns separated by spaces)
    
    Fallback: PyPDF2 for raw text if pdfplumber fails entirely.
    """
    import pdfplumber

    results = []

    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            table_texts = []

            # Method 1: Standard table extraction
            tables = page.extract_tables() or []

            # Method 2: Relaxed settings for borderless tables
            if not tables:
                try:
                    tables = page.extract_tables({
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                        "min_words_vertical": 2,
                        "min_words_horizontal": 2,
                    }) or []
                except Exception:
                    tables = []

            # Process tables → markdown
            for table in tables:
                if not table or len(table) < 2:
                    continue

                max_cols = max(len(row) for row in table if row)
                clean_table = []
                for row in table:
                    if not row:
                        continue
                    clean_row = [(cell or "").strip().replace("\n", " ") for cell in row]
                    while len(clean_row) < max_cols:
                        clean_row.append("")
                    clean_table.append(clean_row)

                if len(clean_table) < 2:
                    continue

                all_content = " ".join(" ".join(r) for r in clean_table).strip()
                if not all_content:
                    continue

                header = clean_table[0]
                md = "| " + " | ".join(header) + " |\n"
                md += "| " + " | ".join(["---"] * len(header)) + " |\n"
                for row in clean_table[1:]:
                    md += "| " + " | ".join(row[:len(header)]) + " |\n"

                table_md = md.strip()
                table_texts.append(table_md)
                results.append({"page": page_num, "type": "table", "content": table_md})

            # Extract remaining text
            full_text = page.extract_text() or ""

            # Method 3: Line-based table detection
            if not tables and full_text:
                lines = full_text.split("\n")
                potential_table = []
                for line in lines:
                    segments = [s.strip() for s in re.split(r'\s{2,}', line.strip()) if s.strip()]
                    if len(segments) >= 3:
                        potential_table.append(segments)
                    else:
                        if len(potential_table) >= 2:
                            max_c = max(len(r) for r in potential_table)
                            padded = [r + [""] * (max_c - len(r)) for r in potential_table]
                            md = "| " + " | ".join(padded[0]) + " |\n"
                            md += "| " + " | ".join(["---"] * max_c) + " |\n"
                            for row in padded[1:]:
                                md += "| " + " | ".join(row) + " |\n"
                            table_md = md.strip()
                            table_texts.append(table_md)
                            results.append({"page": page_num, "type": "table", "content": table_md})
                        potential_table = []

                if len(potential_table) >= 2:
                    max_c = max(len(r) for r in potential_table)
                    padded = [r + [""] * (max_c - len(r)) for r in potential_table]
                    md = "| " + " | ".join(padded[0]) + " |\n"
                    md += "| " + " | ".join(["---"] * max_c) + " |\n"
                    for row in padded[1:]:
                        md += "| " + " | ".join(row) + " |\n"
                    table_md = md.strip()
                    table_texts.append(table_md)
                    results.append({"page": page_num, "type": "table", "content": table_md})

            # Remove table text from remaining text
            remaining_text = full_text.strip()
            for tt in table_texts:
                for line in tt.split("\n"):
                    clean = line.replace("|", "").replace("---", "").strip()
                    if clean and len(clean) > 3 and clean in remaining_text:
                        remaining_text = remaining_text.replace(clean, "", 1)

            remaining_text = re.sub(r'\n{3,}', '\n\n', remaining_text).strip()
            if remaining_text and len(remaining_text) > 20:
                results.append({"page": page_num, "type": "text", "content": remaining_text})

    # Fallback: PyPDF2
    if not results:
        from PyPDF2 import PdfReader
        reader = PdfReader(file_path)
        for i, page in enumerate(reader.pages):
            txt = page.extract_text() or ""
            if txt.strip():
                results.append({"page": i + 1, "type": "text", "content": txt.strip()})

    return results


# ══════════════════════════════════════════════════════
# STEP 2: SMART CHUNKING
# ══════════════════════════════════════════════════════

def smart_chunk(content_blocks: list[dict], chunk_size: int = 512, chunk_overlap: int = 50) -> list[dict]:
    """
    Tables → never split (single chunk).
    Text → RecursiveCharacterTextSplitter.
    Section titles detected and prepended.
    """
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
    """Embed multiple texts using local sentence-transformers."""
    model = _get_embed_model()
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return [e.tolist() for e in embeddings]

def embed_query(text: str) -> list[float]:
    """Embed a single query with BGE prefix for better retrieval."""
    model = _get_embed_model()
    embedding = model.encode("Represent this sentence: " + text, show_progress_bar=False, normalize_embeddings=True)
    return embedding.tolist()


# ══════════════════════════════════════════════════════
# STEP 4: PGVECTOR SEARCH
# ══════════════════════════════════════════════════════

def pgvector_search(db: Session, space_id: str, query_embedding: list[float], top_k: int) -> list[dict]:
    """
    Search for similar chunks using pgvector's <=> operator.
    
    How it works:
    - <=> is the cosine distance operator (1 - cosine_similarity)
    - Lower distance = more similar
    - pgvector uses IVFFlat index for fast approximate search
    - One SQL query replaces the Python loop over all chunks
    
    Before (Python loop):
        chunks = db.query(Chunk).all()       # load ALL chunks
        for chunk in chunks:                  # loop through ALL
            score = cosine_similarity(...)    # calculate one by one
    
    After (pgvector SQL):
        SELECT * FROM chunks
        ORDER BY embedding <=> query_vector   # pgvector handles it
        LIMIT 5                               # returns only top 5
    
    This is O(log n) instead of O(n).
    """
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
    """Simple keyword matching score for hybrid search."""
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
    """
    Hybrid search: pgvector (semantic) + keyword scoring.
    
    1. pgvector finds top_k * 2 candidates (semantic search in SQL)
    2. Python adds keyword score to each candidate
    3. Combined score: 70% semantic + 30% keyword
    4. Re-sort and return top_k
    
    Why hybrid?
    → pgvector is great for meaning but can miss exact terms
    → keyword catches specific names, dates, numbers
    → combining both gives better results
    """
    # Get more candidates than needed, then re-rank
    candidates = pgvector_search(db, space_id, query_embedding, top_k * 2)

    if not candidates:
        return []

    for c in candidates:
        kw = keyword_score(query_text, c["content"])
        c["keyword_score"] = round(kw, 4)
        c["semantic_score"] = c["score"]

        # Combined: 70% semantic + 30% keyword
        combined = (0.7 * c["score"]) + (0.3 * kw)

        # Boost tables if query mentions table-related words
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
    """Send prompt with context to LLM."""
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

def create_space(db: Session, data: CreateRAGSpaceRequest, org_id: str) -> dict:
    space = RAGSpace(
        name=data.name, description=data.description,
        organization_id=org_id, chunk_size=data.chunk_size,
        chunk_overlap=data.chunk_overlap, top_k=data.top_k,
        chunk_strategy=data.chunk_strategy,
    )
    db.add(space)
    db.commit()
    db.refresh(space)
    return _space_dict(space, db)

def list_spaces(db: Session, org_id: str) -> list[dict]:
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
# UPLOAD — FULL PIPELINE
# ══════════════════════════════════════════════════════

async def upload_document(db: Session, space_id: str, org_id: str, file: UploadFile) -> dict:
    """
    1. Save PDF → temp file
    2. pdfplumber extracts text + tables
    3. Smart chunking
    4. sentence-transformers embeds chunks
    5. Store in PostgreSQL with pgvector
    """
    space = _find_space(db, space_id, org_id)

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    content = await file.read()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.write(content)
    tmp.close()

    doc = Document(
        file_name=file.filename, file_type="pdf",
        file_size=len(content), status=DocStatus.INDEXING,
        rag_space_id=space_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        # Step 1: Extract
        content_blocks = extract_pdf_content(tmp.name)
        if not content_blocks:
            raise Exception("No content found in PDF")

        # Step 2: Chunk
        chunks = smart_chunk(content_blocks, space.chunk_size, space.chunk_overlap)
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
    """
    1. Embed question
    2. pgvector SQL search + keyword re-ranking
    3. Build context
    4. LLM generates answer
    5. Return answer + sources
    """
    space = _find_space(db, space_id, org_id)

    # Step 1: Embed
    query_embedding = embed_query(data.question)

    # Step 2: Hybrid search (pgvector + keyword)
    results = hybrid_search(db, space_id, data.question, query_embedding, space.top_k)

    if not results:
        return {
            "answer": "I don't have any documents to answer this question. Please upload documents first.",
            "sources": [],
        }

    # Get document names
    doc_ids = list(set(r["document_id"] for r in results))
    docs = db.query(Document).filter(Document.id.in_(doc_ids)).all()
    doc_names = {d.id: d.file_name for d in docs}

    # Step 3: Build context
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

    # Step 4: LLM
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

def _space_dict(space: RAGSpace, db: Session = None) -> dict:
    num_docs = 0
    num_chunks = 0
    if db:
        num_docs = db.query(Document).filter(Document.rag_space_id == space.id).count()
        num_chunks = db.query(Chunk).filter(Chunk.rag_space_id == space.id).count()
    return {
        "id": space.id, "name": space.name, "description": space.description,
        "organization_id": space.organization_id, "chunk_size": space.chunk_size,
        "chunk_overlap": space.chunk_overlap, "top_k": space.top_k,
        "chunk_strategy": space.chunk_strategy, "num_documents": num_docs,
        "num_chunks": num_chunks, "created_at": str(space.created_at),
    }

def _doc_dict(doc: Document) -> dict:
    return {
        "id": doc.id, "file_name": doc.file_name, "file_type": doc.file_type,
        "file_size": doc.file_size, "num_chunks": doc.num_chunks,
        "status": doc.status, "error_msg": doc.error_msg,
        "rag_space_id": doc.rag_space_id, "uploaded_at": str(doc.uploaded_at),
    }