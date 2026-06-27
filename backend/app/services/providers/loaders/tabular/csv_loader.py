"""
CSV Loader — uses pandas to read CSV, converts to markdown table format.

The loader's job is only to produce clean raw_text + metadata. The decision
about how to chunk a CSV (one table vs. one section per row) is made later by
csv_parser.py based on size.

Why markdown here: even the raw_text preview needs column headers so a human
reviewing the loaded text can tell what each value means. "25000" alone is
ambiguous; "Salary | 25000" is clear.
"""
import os
import logging

logger = logging.getLogger(__name__)


def load(file_path: str) -> dict:
    logger.info(f"[CSV_LOADER] Loading: {os.path.basename(file_path)}")

    try:
        import pandas as pd
        df = pd.read_csv(file_path, encoding="utf-8", on_bad_lines="skip")
        raw_text = df.to_markdown(index=False)
        metadata = {
            "source": os.path.basename(file_path),
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": ", ".join(str(c) for c in df.columns.tolist()),
        }
    except Exception as e:
        logger.warning(f"Pandas CSV failed: {e}, falling back to raw read")
        raw_text, metadata = _fallback_read(file_path)

    if not raw_text.strip():
        raise ValueError("CSV file is empty")

    return {
        "raw_text": raw_text,
        "num_pages": 1,
        "file_type": "CSV",
        "category": "table",
        "metadata": metadata,
        "total_chars": len(raw_text),
        # Pass the path through so the parser can read structured rows directly.
        "file_path": os.path.abspath(file_path),
    }


def _fallback_read(file_path: str) -> tuple:
    """Fallback: read CSV as pipe-separated text."""
    import csv
    rows = []
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for row in csv.reader(f):
            rows.append(" | ".join(row))
    return "\n".join(rows), {"source": os.path.basename(file_path)}