"""
Vanna layer — SQL intelligence.

    store.py     our Vanna vector store (data_vectors_<dim> + hybrid search)
    client.py    store + LLM composition, instance cache, SAFE run_sql
    training.py  builds the three knowledge indexes
    prompts.py   default / custom rules, correction and answer templates

Vanna owns retrieval + prompt + generation. Orchestration, validation and
execution belong to LangGraph and the validators — never to Vanna.
"""
from .client import evict, get_client  # noqa: F401
from .prompts import (build_answer_prompt, build_correction_prompt,  # noqa: F401
                      build_system_rules)
from .training import start_training  # noqa: F401
