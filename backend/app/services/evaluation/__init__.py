"""
Evaluation package — the trust-first evaluation stack.

  common.py            shared constants + reasoning-model fixes
  datasets/
    loader.py          pandas/openpyxl → eval_cases (CRUD, parsing, templates)
    generator.py       Ragas TestsetGenerator (source='generated'), LLM fallback
  scoring/
    retrieval.py       ranx — Recall@K / Precision@K / MRR / NDCG (no AI)
    generation.py      Ragas (LLM-as-judge framework) + single-call fallback
    performance.py     latency / tokens / cost — litellm cost map
    judge.py           independent judge LLM (company / local / own key)
  runner.py            orchestrates the experiment (worker fan-out) + history

Routes import this package as one facade:
    from app.services import evaluation as eval_service
"""
from .common import CATEGORIES, PLAIN_TYPES                       # noqa: F401
from .scoring import judge_llm, judge_correctness                 # noqa: F401
from .datasets import (                                           # noqa: F401
    list_cases, add_case, upload_dataset, delete_case, clear_cases,
    parse_dataset_file, dataset_template, template_excel, expert_form_html,
    generate_cases,
)
from .runner import (run_evaluation, start_evaluation, job_status,  # noqa: F401
                     list_runs, get_run)
