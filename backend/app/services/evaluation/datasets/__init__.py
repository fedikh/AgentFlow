"""Datasets package — building the test set.

    loader.py     pandas/openpyxl → eval_cases (CRUD, parsing, templates)
    generator.py  Ragas TestsetGenerator (source='generated'), LLM fallback
"""
from .loader import (                                    # noqa: F401
    list_cases, add_case, upload_dataset, delete_case, clear_cases,
    parse_dataset_file, dataset_template, template_excel, expert_form_html,
)
from .generator import generate_cases                    # noqa: F401
