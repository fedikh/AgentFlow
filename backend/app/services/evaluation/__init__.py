"""
Evaluation package — the trust-first evaluation stack.

  common.py       shared constants, price table, reasoning-model fixes
  datasets.py     case CRUD · expert templates (HTML form / Excel / JSON)
                  · file parsing (.xlsx/.csv/.json, EN+FR) · generation
  judge.py        independent judge LLM (GPT-5 / Claude / Gemini / same)
  ragas_engine.py Ragas context+answer scoring, judge fallback
  metrics.py      custom retrieval math (Recall/Precision/MRR/NDCG),
                  weighted overall score, rule-engine recommendations
  runner.py       the experiment runner + runs history

Routes import this package as one facade:
    from app.services import evaluation as eval_service
"""
from .common import CATEGORIES, PLAIN_TYPES                       # noqa: F401
from .judge import JUDGE_PRESETS, judge_llm, judge_correctness    # noqa: F401
from .datasets import (                                           # noqa: F401
    list_cases, add_case, upload_dataset, delete_case, clear_cases,
    parse_dataset_file, dataset_template, template_excel, expert_form_html,
    generate_cases,
)
from .runner import run_evaluation, list_runs, get_run            # noqa: F401
