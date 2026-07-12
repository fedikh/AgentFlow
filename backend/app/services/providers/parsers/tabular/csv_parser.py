"""
CSV Parser — Table Document Model (pandas).

Produces a rich `table` element (schema + typed rows) for structure/citations,
AND chunking blocks for the Chunking Factory:
  • small CSV → one Table block (kept intact for table-scan lookups)
  • large CSV → one Section per row ("Col: Value | …") for precise retrieval
"""
import os
import logging
import pandas as pd
from app.services.providers.parsers.parsed_document import ParsedDocument, Section, Table

logger = logging.getLogger(__name__)

LARGE_CSV_CHAR_THRESHOLD = 4000
ROWS_PER_SECTION = 1


def parse(loaded_data: dict) -> ParsedDocument:
    file_path = loaded_data.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise ValueError("CSV parser needs the original file (file_path)")

    logger.info("[CSV_PARSER] Parsing CSV → table element")
    df = pd.read_csv(file_path, on_bad_lines="skip")

    table_name = os.path.splitext(loaded_data.get("metadata", {}).get("source")
                                  or os.path.basename(file_path))[0]

    from app.services.providers.parsers.table_elements import build_csv_elements
    elements, _text = build_csv_elements(df, table_name)

    # ── Chunking blocks (unchanged behaviour) ──
    markdown = df.to_markdown(index=False)
    sections, tables = [], []
    if len(markdown) <= LARGE_CSV_CHAR_THRESHOLD:
        tables = [Table(content=markdown, headers=[str(c) for c in df.columns],
                        rows=df.values.tolist(), num_rows=len(df),
                        num_cols=len(df.columns), page=1)]
    else:
        headers = [str(c) for c in df.columns]
        for start in range(0, len(df), ROWS_PER_SECTION):
            batch = df.iloc[start:start + ROWS_PER_SECTION]
            lines = [" | ".join(f"{h}: {'' if pd.isna(v) else v}"
                                for h, v in zip(headers, row))
                     for row in batch.values.tolist()]
            first, last = start + 1, start + len(batch)
            heading = f"Row {first}" if len(batch) == 1 else f"Rows {first}-{last}"
            sections.append(Section(heading=heading, content="\n".join(lines), level=1, page=1))

    meta = dict(loaded_data.get("metadata", {}))
    meta.update({"source_type": "csv", "encoding": "utf-8"})

    return ParsedDocument(
        title=table_name, sections=sections, tables=tables, elements=elements,
        metadata=meta, num_pages=1, file_type="CSV", category="structured_data",
    )
