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

    # .xlsx → openpyxl; legacy binary .xls → xlrd (openpyxl cannot read BIFF)
    is_xls = str(file_path).lower().endswith(".xls")
    engine = "xlrd" if is_xls else "openpyxl"
    dfs = pd.read_excel(file_path, sheet_name=None, engine=engine)

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

    from app.services.providers.loaders._utils import build_doc_metadata
    metadata = build_doc_metadata(file_path, len(parts), "xls" if is_xls else "xlsx",
                                  parser_name=engine,
                                  extra={"num_sheets": len(sheet_names), "total_rows": total_rows})

    return {
        "raw_text": raw_text,
        "num_pages": len(parts),
        "file_type": "Excel",
        "category": "table",
        "metadata": metadata,
        "total_chars": len(raw_text),
        # Pass the path through so the parser can read the workbook structure.
        "file_path": os.path.abspath(file_path),
    }
