"""
Excel Loader — uses pandas + openpyxl.
Loads all sheets, each converted to markdown table.
"""
import os
import logging

logger = logging.getLogger(__name__)


def load(file_path: str) -> dict:
    logger.info(f"[EXCEL_LOADER] Loading: {os.path.basename(file_path)}")

    import pandas as pd

    dfs = pd.read_excel(file_path, sheet_name=None, engine="openpyxl")

    if not dfs:
        raise ValueError("Excel file has no sheets or is empty")

    parts = []
    total_rows = 0
    sheet_names = []

    for sheet_name, df in dfs.items():
        if df.empty:
            continue
        md = df.to_markdown(index=False)
        parts.append(f"[Sheet: {sheet_name}]\n{md}")
        total_rows += len(df)
        sheet_names.append(sheet_name)

    if not parts:
        raise ValueError("All Excel sheets are empty")

    raw_text = "\n\n".join(parts)

    return {
        "raw_text": raw_text,
        "num_pages": len(parts),
        "file_type": "Excel",
        "category": "table",
        "metadata": {
            "sheets": ", ".join(sheet_names),
            "total_rows": total_rows,
            "num_sheets": len(sheet_names),
        },
        "total_chars": len(raw_text),
    }
