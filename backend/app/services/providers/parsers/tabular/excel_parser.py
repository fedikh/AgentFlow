"""
Excel Parser — one Table per sheet with structured rows.
"""
import re
import logging
import pandas as pd
from app.services.providers.parsers.parsed_document import ParsedDocument, Table

logger = logging.getLogger(__name__)


def parse(loaded_data: dict) -> ParsedDocument:
    file_path = loaded_data.get("file_path")
    raw_text = loaded_data.get("raw_text", "")

    if not file_path and not raw_text:
        raise ValueError("No Excel data")

    logger.info(f"[EXCEL_PARSER] Parsing Excel")

    tables = []

    # Read structured data from file
    if file_path:
        try:
            dfs = pd.read_excel(file_path, sheet_name=None, engine="openpyxl")
            for sheet_name, df in dfs.items():
                if df.empty:
                    continue

                headers = df.columns.tolist()
                rows = df.values.tolist()
                rows = [[None if pd.isna(v) else v for v in row] for row in rows]
                md = f"[Sheet: {sheet_name}]\n{df.to_markdown(index=False)}"

                tables.append(Table(
                    content=md,
                    headers=headers,
                    rows=rows,
                    num_rows=len(rows),
                    num_cols=len(headers),
                    page=1,
                ))

            if tables:
                sheet_names = [list(dfs.keys())]
                return ParsedDocument(
                    tables=tables,
                    metadata=loaded_data.get("metadata", {}),
                    file_type="Excel",
                    category="table",
                )
        except Exception as e:
            logger.warning(f"Pandas Excel read failed: {e}, using raw text")

    # Fallback: parse from raw text
    if raw_text:
        parts = re.split(r"(\[Sheet:\s*[^\]]+\])", raw_text)
        current_sheet = "Sheet1"

        for part in parts:
            part = part.strip()
            if not part:
                continue
            match = re.match(r"\[Sheet:\s*([^\]]+)\]", part)
            if match:
                current_sheet = match.group(1).strip()
                continue

            lines = [l for l in part.split("\n") if l.strip()]
            headers = []
            if lines and "|" in lines[0]:
                headers = [h.strip() for h in lines[0].split("|") if h.strip()]

            tables.append(Table(
                content=f"[Sheet: {current_sheet}]\n{part}",
                headers=headers,
                rows=[],
                num_rows=max(0, len(lines) - 2),
                num_cols=len(headers),
                page=1,
            ))

    return ParsedDocument(
        tables=tables,
        metadata=loaded_data.get("metadata", {}),
        file_type="Excel",
        category="table",
    )