"""
CSV Parser — produces ParsedDocument with structured rows.
"""
import logging
import pandas as pd
from app.services.providers.parsers.parsed_document import ParsedDocument, Table

logger = logging.getLogger(__name__)


def parse(loaded_data: dict) -> ParsedDocument:
    raw_text = loaded_data.get("raw_text", "")
    file_path = loaded_data.get("file_path")

    if not raw_text.strip() and not file_path:
        raise ValueError("No CSV data")

    logger.info(f"[CSV_PARSER] Parsing CSV")

    # Read structured data from file if available
    rows = []
    headers = []

    if file_path:
        try:
            df = pd.read_csv(file_path, encoding="utf-8", on_bad_lines="skip")
            headers = df.columns.tolist()
            rows = df.values.tolist()
            # Convert NaN to None for clean JSON
            rows = [[None if pd.isna(v) else v for v in row] for row in rows]
            # Build markdown content
            raw_text = df.to_markdown(index=False)
        except Exception as e:
            logger.warning(f"Pandas read failed: {e}, using raw text")

    # Fallback: extract from raw text
    if not headers and raw_text:
        lines = raw_text.strip().split("\n")
        if lines and "|" in lines[0]:
            headers = [h.strip() for h in lines[0].split("|") if h.strip()]

    tables = [Table(
        content=raw_text.strip(),
        headers=headers,
        rows=rows,
        num_rows=len(rows),
        num_cols=len(headers),
        page=1,
    )]

    return ParsedDocument(
        tables=tables,
        metadata=loaded_data.get("metadata", {}),
        file_type="CSV",
        category="table",
    )