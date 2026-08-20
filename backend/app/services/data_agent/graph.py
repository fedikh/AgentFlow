"""
The LangGraph workflow — Vanna owns SQL intelligence, LangGraph owns
control flow and state.

                 ┌──────────┐
                 │ analyze  │  not a data question ─────────────┐
                 └────┬─────┘                                   │
                      ▼                                         │
                ┌───────────┐                                   │
           ┌───▶│ generate  │                                   │
           │    └─────┬─────┘                                   │
           │          ▼                                         │
           │    ┌───────────┐   invalid & attempts < MAX        │
           │    │ validate  ├──────────────┐                    │
           │    └─────┬─────┘              ▼                    │
           │          │ valid         ┌─────────┐               │
           │          │               │ correct │               │
           │          │               └────┬────┘               │
           │          │                    │ (back to validate) │
           │          ▼                    │                    │
           │    ┌───────────┐              │                    │
           │    │  execute  │◀─────────────┘                    │
           │    └─────┬─────┘                                   │
           │          ▼                                         │
           │  ┌────────────────┐                                │
           │  │ analyze_result │                                │
           │  └───────┬────────┘                                │
           │          ▼                                         │
           │    ┌───────────┐                                   │
           └───▶│  answer   │◀──────────────────────────────────┘
                └─────┬─────┘
                      ▼  END

The retry cap lives in ONE routing function — there is no other way to
re-enter correction, so an infinite loop is structurally impossible.
`recursion_limit` is a second, independent ceiling.
"""
from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from app.services.data_agent.nodes import (analyze, analyze_result,
                                           answer_from_documents, correct_sql,
                                           execute_sql, generate_answer,
                                           generate_sql, validate_sql)
from app.services.data_agent.state import AgentState, new_state

logger = logging.getLogger(__name__)

MAX_RETRIES = 3            # hard ceiling — configurable DOWNWARD only
RECURSION_LIMIT = 15       # belt and braces


def _has_documents(source_id: str) -> bool:
    from app.database import SessionLocal
    from app.models.data_agent import DataSource
    from app.services.data_agent.nodes.answer_documents import has_documents
    db = SessionLocal()
    try:
        source = db.query(DataSource).filter(DataSource.id == source_id).first()
        return bool(source) and has_documents(db, source)
    except Exception:
        return False
    finally:
        db.close()


def _route_after_analyze(state: AgentState) -> str:
    intent = state.get("intent") or ("data" if state.get("is_data_question", True)
                                     else "smalltalk")
    if intent == "data":
        return "generate"
    if intent == "documents":
        return "documents"
    return "answer"


def _route_after_validate(state: AgentState) -> str:
    """The ONLY place the correction loop can be re-entered."""
    if state.get("insufficient"):
        # The schema honestly cannot answer. If the agent has business
        # documents, try THEM before giving up — that is the RAG path.
        return "documents" if _has_documents(state["source_id"]) else "answer"
    if state.get("valid"):
        return "execute"
    max_attempts = int(state.get("max_attempts") or MAX_RETRIES)
    if int(state.get("attempts", 0)) >= max_attempts:
        return "answer"                       # exhausted — honest failure
    return "correct"


def _build():
    g = StateGraph(AgentState)
    g.add_node("analyze", analyze)
    g.add_node("generate", generate_sql)
    g.add_node("validate", validate_sql)
    g.add_node("correct", correct_sql)
    g.add_node("execute", execute_sql)
    g.add_node("analyze_result", analyze_result)
    g.add_node("documents", answer_from_documents)
    g.add_node("answer", generate_answer)

    g.set_entry_point("analyze")
    g.add_conditional_edges("analyze", _route_after_analyze,
                            {"generate": "generate", "documents": "documents",
                             "answer": "answer"})
    g.add_edge("generate", "validate")
    g.add_conditional_edges("validate", _route_after_validate,
                            {"execute": "execute", "correct": "correct",
                             "documents": "documents", "answer": "answer"})
    g.add_edge("correct", "validate")          # the bounded cycle
    g.add_edge("execute", "analyze_result")
    g.add_edge("analyze_result", "answer")
    g.add_edge("documents", "answer")          # RAG path joins the same exit
    g.add_edge("answer", END)
    return g.compile()


GRAPH = _build()                               # compiled once at import


def run(source_id: str, question: str, max_attempts: int = MAX_RETRIES) -> AgentState:
    state = new_state(source_id, question)
    state["max_attempts"] = max(1, min(int(max_attempts), MAX_RETRIES))
    return GRAPH.invoke(state, config={"recursion_limit": RECURSION_LIMIT})
