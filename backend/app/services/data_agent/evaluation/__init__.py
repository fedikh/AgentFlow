"""
Data Agent evaluation — public facade (the eval_service pattern).

    cases       CRUD · import from verified examples · file upload · verify
    generator   LLM-proposed cases from the schema catalog (human-verified)
    runner      execution-accuracy experiments + run history
    comparison  pure result-set comparison (the scoring core)
"""
from .cases import (CATEGORIES, add_case, clear_cases, dataset_template,  # noqa: F401
                    delete_case, import_from_examples, list_cases,
                    parse_dataset_file, update_case, upload_dataset,
                    verify_case)
from .comparison import compare_results  # noqa: F401
from .generator import generate_cases  # noqa: F401
from .runner import (delete_run, get_run, list_runs, run_evaluation,  # noqa: F401
                     start_run)
