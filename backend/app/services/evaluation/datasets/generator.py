"""
Datasets — generator: synthetic test cases (source='generated').

Ragas TestsetGenerator over real indexed chunks (the space's own LLM +
embedder), with a chunk-grounded single-LLM fallback when Ragas is
unavailable. 150s budget so generation can never hang a request.
"""
from __future__ import annotations

from fastapi import HTTPException

from ..common import logger, CATEGORIES, json_from, space_llm
from .loader import add_case

def _generate_native(db, space, n: int) -> list:
    from sqlalchemy import text as T
    rows = db.execute(T("""
        SELECT c.content, c.page, d.file_name
        FROM chunks c JOIN documents d ON d.id = c.document_id
        WHERE c.rag_space_id = :sid AND length(c.content) > 200
        ORDER BY random() LIMIT :n
    """), {"sid": space.id, "n": max(3, min(n, 15))}).fetchall()
    if not rows:
        raise HTTPException(400, "No indexed chunks — process documents first")
    llm = space_llm(db, space, max_tokens=1600)
    created = []
    for r in rows[:n]:
        prompt = (
            "You create ONE evaluation test case for a RAG system from this "
            "document excerpt. Reply ONLY with JSON: {\"question\": str, "
            "\"expected_answer\": str (short, directly supported by the text), "
            f"\"category\": one of {CATEGORIES}, "
            "\"difficulty\": easy|medium|hard, \"language\": ISO code like fr/en}. "
            "Use the excerpt's language.\n\n"
            f"Document: {r.file_name} (page {r.page})\nExcerpt:\n{r.content[:1500]}"
        )
        try:
            out = json_from(getattr(llm.invoke(prompt), "content", ""))
            if not out or not out.get("question"):
                continue
            created.append(add_case(db, space.id, {
                **out,
                "expected_document": r.file_name,
                "expected_page": r.page,
            }, source="generated"))
        except Exception as e:
            logger.warning(f"[EVAL] native generation failed on one chunk: {e}")
    return created


def _generate_ragas(db, space, n: int) -> list | None:
    """Ragas TestsetGenerator over real chunks; None on any failure. 150s budget."""
    import concurrent.futures as cf

    def _work():
        from sqlalchemy import text as T
        from langchain_core.documents import Document
        from ragas.testset import TestsetGenerator
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from app.services.embedding_factory.resolver import resolve_embedding_config
        from app.services.embedding_factory.factory import get_embedder

        rows = db.execute(T("""
            SELECT c.content, c.page, d.file_name
            FROM chunks c JOIN documents d ON d.id = c.document_id
            WHERE c.rag_space_id = :sid AND length(c.content) > 300
            ORDER BY random() LIMIT 25
        """), {"sid": space.id}).fetchall()
        if len(rows) < 3:
            return None
        docs = [Document(page_content=r.content[:2500],
                         metadata={"file_name": r.file_name, "page": r.page})
                for r in rows]
        llm = LangchainLLMWrapper(space_llm(db, space, max_tokens=2500))
        conf = resolve_embedding_config(db, space)
        emb = LangchainEmbeddingsWrapper(get_embedder(
            conf["family"], conf["model"], conf.get("api_key", ""), conf.get("base_url", "")))
        gen = TestsetGenerator(llm=llm, embedding_model=emb)
        ds = gen.generate_with_langchain_docs(docs, testset_size=min(n, 10))

        def source_of(sample):
            """Trace a generated question back to its source chunk so the
            case gets a RETRIEVAL LABEL (expected_document/page) — without it
            the whole retrieval family is unscored. Ragas keeps the chunk
            texts in reference_contexts; match them to the rows we fed in."""
            for ctx in (getattr(sample, "reference_contexts", None) or []):
                for r in rows:
                    if r.content[:150] in ctx or (ctx or "")[:150] in r.content:
                        return r.file_name, r.page
            return None, None

        out = []
        for s in ds.samples:
            d = s.eval_sample
            q = getattr(d, "user_input", None)
            if not q:
                continue
            doc_name, page = source_of(d)
            out.append({
                "question": q,
                "expected_answer": getattr(d, "reference", None),
                "expected_document": doc_name,
                "expected_page": page,
                "category": "semantic",
            })
        return out or None

    try:
        with cf.ThreadPoolExecutor(max_workers=1) as pool:
            raw = pool.submit(_work).result(timeout=150)
        if not raw:
            return None
        return [add_case(db, space.id, r, source="generated") for r in raw]
    except Exception as e:
        logger.warning(f"[EVAL] ragas testset generation unavailable ({e}) — native fallback")
        return None


def generate_cases(db: Session, space, n: int = 8) -> dict:
    cases = _generate_ragas(db, space, n)
    engine = "ragas"
    if not cases:
        cases = _generate_native(db, space, n)
        engine = "llm"
    if not cases:
        raise HTTPException(500, "Generation produced no cases (check the space LLM key)")
    return {"cases": cases, "engine": engine}
