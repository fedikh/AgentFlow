"""
Graph nodes — one file per step, each a pure function State → State.

    analyze          is it a data question? normalize it
    generate_sql     Vanna: retrieve (hybrid) → prompt → LLM → extract
    validate_sql     the five-check chain; returns the SAFE SQL
    correct_sql      feed the exact validator error back to the model
    execute_sql      read-only session, timeout, EXPLAIN, bounded fetch
    analyze_result   honest observations about the rows
    generate_answer  the final message (never a fabricated one)
"""
from .analyze import analyze  # noqa: F401
from .analyze_result import analyze_result  # noqa: F401
from .answer_documents import answer_from_documents, has_documents  # noqa: F401
from .correct_sql import correct_sql  # noqa: F401
from .execute_sql import execute_sql, run_validated  # noqa: F401
from .generate_answer import generate_answer  # noqa: F401
from .generate_sql import SENTINEL, generate_sql  # noqa: F401
from .validate_sql import validate_sql  # noqa: F401
