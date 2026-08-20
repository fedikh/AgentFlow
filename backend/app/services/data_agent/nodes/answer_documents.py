"""
Node — ANSWER FROM DOCUMENTS.

Not every question about a database is a SQL question. "What does
'collaborateur RH' mean?" or "What is our refund policy?" is answered by the
business documents, not by a SELECT. Forcing SQL there produces a nonsense
join; refusing produces a dead end.

So the agent has a second answering path, and it is the RAG one:
retrieval over the agent's knowledge space (services/retrieval) + the same
`generate_answer` the RAG spaces use. Identical behaviour, identical
quality — because it is literally the same code.

Reached in two ways (graph.py):
  · directly, when the question is clearly definitional
  · as a FALLBACK, when SQL generation answered INSUFFICIENT_SCHEMA and the
    agent has documents — the honest refusal becomes a real answer
"""
from __future__ import annotations

import logging
import time

from app.services.data_agent.state import AgentState, stamp

logger = logging.getLogger(__name__)

MAX_CONTEXT_CHUNKS = 8


def has_documents(db, source) -> bool:
    """Does this agent have any indexed document knowledge?"""
    from app.models.document import Document
    from app.services.data_agent.knowledge.space import get_space
    space = get_space(db, source)
    if space is None:
        return False
    return bool(db.query(Document)
                .filter(Document.rag_space_id == space.id,
                        Document.num_chunks > 0).first())


def answer_from_documents(state: AgentState) -> AgentState:
    from app.database import SessionLocal
    from app.models.data_agent import DataSource
    from app.services.data_agent.config import retrieval_config
    from app.services.data_agent.retrieval.hybrid import retrieve_documents
    from app.services.llm_factory import generate_answer

    t0 = time.perf_counter()
    db = SessionLocal()
    try:
        source = db.query(DataSource).filter(
            DataSource.id == state["source_id"]).first()
        chunks = retrieve_documents(db, source, state["question"],
                                    retrieval_config(source))[:MAX_CONTEXT_CHUNKS]
        if not chunks:
            # nothing to ground on — keep whatever the SQL path concluded
            state.setdefault("doc_sources", [])
            if not state.get("answer") and not state.get("insufficient"):
                state["answer"] = ("I couldn't find anything about this in the "
                                   "connected data or the uploaded documents.")
            stamp(state, "answer_documents", t0)
            return state

        context = "\n\n---\n\n".join(
            f"[Source {i + 1}: {c.document_id}]\n{c.content}"
            for i, c in enumerate(chunks))
        sources_info = "\n".join(
            f"Source {i + 1}: {c.document_id}" for i, c in enumerate(chunks))

        state["answer"] = generate_answer(db, source, state["question"],
                                          context, sources_info)
        state["answered_from"] = "documents"
        state["doc_sources"] = [{"document": c.document_id, "page": c.page,
                                 "score": c.score, "method": c.method}
                                for c in chunks]
        state["insufficient"] = ""            # answered after all
    except Exception as e:
        logger.warning(f"[DATA-AGENT/documents] {e!r}")
        if not state.get("answer"):
            state["answer"] = ("I couldn't answer this from the documents: "
                               f"{str(e)[:200]}")
    finally:
        db.close()
    stamp(state, "answer_documents", t0)
    return state
