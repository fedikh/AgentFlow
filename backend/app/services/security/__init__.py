"""
Security evaluation package — the second, symmetric evaluation engine.

Replays a FROZEN attack corpus through the real RAG pipeline, decides each case
with deterministic checkers then an independent judge, computes a severity-
weighted robustness score, and maps every failing category to a concrete config
fix. Uses the SAME judge LLM resolution as the quality evaluation (company /
local / own key).

  catalog.py    category metadata + the static recommendation table
  seed.py       the frozen bilingual attack corpus (seeded once)
  checkers.py   deterministic verifiers (prompt-leak, PII, invented source)
  judge.py      the security judge (reuses the eval judge LLM)
  scoring.py    weighted robustness + per-category attack success rate
  recommend.py  failing category → config diff (no LLM)
  executor.py   the campaign runner (real pipeline, parallel 5, async jobs)
  compare.py    two campaigns side by side (corrected / regressed)
"""
from app.models.security import CATEGORIES, SEVERITIES  # noqa: F401
from .catalog import CATEGORY_META  # noqa: F401
from .seed import seed_corpus  # noqa: F401
from .executor import (delete_run, get_run, job_status, list_runs,  # noqa: F401
                       manual_batch, manual_check, retry_case, run_security,
                       start_run)
from .compare import compare_runs, list_cases  # noqa: F401
