"""
Node 2 — GENERATE SQL.

Vanna does four things inside one call:
    retrieve   the three indexes (hybrid: vector + keyword + RRF)
    prompt     DDLs · business context · few-shot pairs · our rules
    LLM        temperature from the agent's config
    extract    strip fences/prose, return bare SQL

We record WHAT was retrieved into the state — that is the explainability
payload the UI shows and the trace stored on the message.

INSUFFICIENT_SCHEMA is a first-class outcome, not an error: it means the
model correctly refused to invent. It short-circuits to the answer node
unmodified.
"""
from __future__ import annotations

import logging
import time

from app.services.data_agent.state import AgentState, stamp

logger = logging.getLogger(__name__)

SENTINEL = "INSUFFICIENT_SCHEMA"


def generate_sql(state: AgentState) -> AgentState:
    from app.database import SessionLocal
    from app.models.data_agent import DataSource
    from app.services.data_agent.config import retrieval_config
    from app.services.data_agent.retrieval.hybrid import retrieve_all
    from app.services.data_agent.vanna.client import get_client

    t0 = time.perf_counter()
    db = SessionLocal()
    try:
        source = db.query(DataSource).filter(
            DataSource.id == state["source_id"]).first()
        vn = get_client(db, source)
        question = state["question"]

        # explainability: what the RAG index returned for this question
        try:
            cfg = retrieval_config(source)
            retrieved = retrieve_all(db, source, question, cfg,
                                     vn.generate_embedding(question))
            state["retrieval"] = {
                k: [{"content": c.content[:300], "method": c.method,
                     "score": c.score} for c in v]
                for k, v in retrieved.items()}
        except Exception as e:
            logger.warning(f"[DATA-AGENT/trace] retrieval preview failed: {e!r}")

        sql = (vn.generate_sql(question=question,
                               allow_llm_to_see_data=False) or "").strip()
        state["sql"] = sql
        state["attempts"] = int(state.get("attempts", 0)) + 1
        if SENTINEL in sql:
            state["insufficient"] = sql
    except Exception as e:
        logger.warning(f"[DATA-AGENT/generate] {e!r}")
        state["sql"] = ""
        state["attempts"] = int(state.get("attempts", 0)) + 1
        state.setdefault("errors", []).append(f"generation failed: {e}")
    finally:
        db.close()
    stamp(state, f"generate_{state.get('attempts', 1)}", t0)
    return state
