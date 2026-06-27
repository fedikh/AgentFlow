"""
CSV Parser — produces ParsedDocument from CSV data.

TWO MODES (decided by size):
  • SMALL CSV  → one Table block (full grid kept intact, good for lookups
                 like "who manages Sales?" where the LLM scans the table).
  • LARGE CSV  → one Section per row, formatted "Col: Value | Col: Value".
                 Each row embeds independently and carries its column labels,
                 so a retrieved chunk is self-explanatory instead of a bare
                 "Alice | 30 | Engineering" with no context.

Why "Column: Value": a lone value like "25000" is ambiguous. Pairing it with
its header — "Salary: 25000" — is what lets the embedding and the LLM know
what the number means.
"""
import logging
import pandas as pd
from app.services.providers.parsers.parsed_document import ParsedDocument, Section, Table

logger = logging.getLogger(__name__)

# If the full markdown table is longer than this many characters, switch to
# row-per-section mode so we don't create one enormous unsearchable chunk.
LARGE_CSV_CHAR_THRESHOLD = 4000

# In large mode, how many rows to group into a single Section. 1 = one row per
# section (most precise retrieval). Raise it to pack a few rows per chunk.
ROWS_PER_SECTION = 1


def parse(loaded_data: dict) -> ParsedDocument:
    raw_text = loaded_data.get("raw_text", "")
    file_path = loaded_data.get("file_path")

    if not raw_text.strip() and not file_path:
        raise ValueError("No CSV data")

    logger.info("[CSV_PARSER] Parsing CSV")

    headers, rows, markdown = _read_csv(file_path, raw_text)

    # Decide mode by the size of the rendered table.
    if markdown and len(markdown) <= LARGE_CSV_CHAR_THRESHOLD:
        return _parse_small(headers, rows, markdown, loaded_data)

    return _parse_large(headers, rows, markdown, loaded_data)


# ══════════════════════════════════════════════════════
# READ — pandas first, fall back to raw text
# ══════════════════════════════════════════════════════

def _read_csv(file_path, raw_text):
    """Return (headers, rows, markdown). rows is a list of lists, NaN→None."""
    headers, rows, markdown = [], [], raw_text.strip()

    if file_path:
        try:
            df = pd.read_csv(file_path, encoding="utf-8", on_bad_lines="skip")
            headers = df.columns.tolist()
            rows = [
                [None if pd.isna(v) else v for v in row]
                for row in df.values.tolist()
            ]
            markdown = df.to_markdown(index=False)
            return headers, rows, markdown
        except Exception as e:
            logger.warning(f"[CSV_PARSER] Pandas read failed: {e}, using raw text")

    # Fallback: pull headers out of the first line of the markdown/pipe text.
    if not headers and markdown:
        lines = markdown.split("\n")
        if lines and "|" in lines[0]:
            headers = [h.strip() for h in lines[0].split("|") if h.strip()]

    return headers, rows, markdown


# ══════════════════════════════════════════════════════
# SMALL — one Table block (current behaviour)
# ══════════════════════════════════════════════════════

def _parse_small(headers, rows, markdown, loaded_data):
    tables = [Table(
        content=markdown,
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


# ══════════════════════════════════════════════════════
# LARGE — one Section per row, "Col: Value | Col: Value"
# ══════════════════════════════════════════════════════

def _parse_large(headers, rows, markdown, loaded_data):
    logger.info(f"[CSV_PARSER] Large CSV → row-per-section ({len(rows)} rows)")

    # If pandas couldn't give structured rows, we can't do row mode safely —
    # fall back to a single table so we never lose the data.
    if not rows or not headers:
        logger.warning("[CSV_PARSER] No structured rows; falling back to single table")
        return _parse_small(headers, rows, markdown, loaded_data)

    sections = []
    for start in range(0, len(rows), ROWS_PER_SECTION):
        batch = rows[start:start + ROWS_PER_SECTION]
        lines = [_row_to_text(headers, r) for r in batch]
        content = "\n".join(lines)

        first = start + 1
        last = start + len(batch)
        heading = f"Row {first}" if len(batch) == 1 else f"Rows {first}–{last}"

        sections.append(Section(
            heading=heading,
            content=content,
            level=1,
            page=1,
        ))

    return ParsedDocument(
        sections=sections,
        metadata={**loaded_data.get("metadata", {}), "csv_mode": "row_per_section"},
        file_type="CSV",
        category="table",
    )


def _row_to_text(headers, row) -> str:
    """One row → 'Name: Alice | Age: 30 | Department: Engineering'."""
    parts = []
    for i, col in enumerate(headers):
        val = row[i] if i < len(row) else ""
        if val is None:
            val = ""
        parts.append(f"{col}: {val}")
    return " | ".join(parts)