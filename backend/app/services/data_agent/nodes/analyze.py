"""
Node 1 — ANALYZE.

Two jobs, in order of cost:
  1. Is this a data question at all? A greeting or a thank-you must never
     reach SQL generation — it wastes a model call and risks an absurd
     query. A cheap deterministic check handles the obvious cases with ZERO
     latency; anything else is treated as a data question (the honest
     default: the pipeline can still answer INSUFFICIENT_SCHEMA).
  2. Normalize the question (whitespace, trailing punctuation) so the same
     wording produces the same retrieval.

Deliberately NOT an LLM call: adding ~1s to every question to catch "hello"
is a bad trade. The hook is here if evaluation ever shows it is needed.
"""
from __future__ import annotations

import re
import time

from app.services.data_agent.state import AgentState, stamp

_SMALL_TALK = re.compile(
    r"^\s*(hi|hello|hey|yo|salut|bonjour|bonsoir|coucou|thanks?|thank you|"
    r"merci|ok|okay|d'accord|bye|au revoir|good (morning|evening|night))"
    r"[\s!.?,]*$", re.IGNORECASE)

_HELP = re.compile(r"^\s*(help|aide|what can you do|que peux[- ]tu faire)"
                   r"[\s!.?]*$", re.IGNORECASE)

# Clearly DEFINITIONAL questions — answered from the business documents, not
# by SQL. Kept deliberately narrow: "what is the total revenue?" must stay a
# data question, so only explicit "what does X mean" shapes match here. Every
# other question still tries SQL first and falls back to the documents when
# the schema genuinely cannot answer (INSUFFICIENT_SCHEMA).
_DEFINITION = re.compile(
    r"(c'est quoi|qu'est[- ]ce que|que veut dire|que signifie|définition|"
    r"definition de|what does .+ mean|what is meant by|explique[rz]?\b|"
    r"explain (what|the meaning)|glossaire|documentation)",
    re.IGNORECASE)

# …unless the question also carries a clear measurement signal.
_DATA_SIGNAL = re.compile(
    r"(how many|how much|combien|count|total|sum|average|moyenne|top \d|"
    r"list |liste |per (day|month|year)|par (jour|mois|an)|\bnombre\b)",
    re.IGNORECASE)


def analyze(state: AgentState) -> AgentState:
    t0 = time.perf_counter()
    question = (state.get("question") or "").strip()
    question = re.sub(r"\s+", " ", question)

    if _SMALL_TALK.match(question):
        state["is_data_question"] = False
        state["intent"] = "smalltalk"
        state["analysis"] = {"reason": "small talk — no database access needed"}
        state["answer"] = ("Hello! Ask me a question about your data — for "
                           "example *how many …*, *list the …*, *what is the "
                           "total …*. I write the SQL and always show it.")
    elif _HELP.match(question):
        state["is_data_question"] = False
        state["intent"] = "smalltalk"
        state["analysis"] = {"reason": "capability question"}
        state["answer"] = ("I answer questions about this database in plain "
                           "language: I retrieve the relevant schema, write a "
                           "read-only SQL query, validate it, run it, and show "
                           "you both the results and the SQL.")
    elif _DEFINITION.search(question) and not _DATA_SIGNAL.search(question):
        state["is_data_question"] = False
        state["intent"] = "documents"
        state["analysis"] = {"reason": "definitional — answered from the "
                                       "business documents",
                             "normalized_question": question}
    else:
        state["is_data_question"] = True
        state["intent"] = "data"
        state["analysis"] = {"reason": "treated as a data question",
                             "normalized_question": question}
    state["question"] = question
    stamp(state, "analyze", t0)
    return state
