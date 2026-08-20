"""
Prompts — the rules the model must obey, and the templates that carry the
retrieved knowledge.

Two modes, chosen per agent in the Models panel:
    default   the platform's hardened rules (recommended)
    custom    the IT's own instructions — the SAFETY rules are STILL
              appended, because they are not negotiable: they are what makes
              the validator's job possible and the agent honest.
"""
from __future__ import annotations

LIMIT_KEYWORD = {
    "postgres": "LIMIT n", "mysql": "LIMIT n",
    "mssql": "SELECT TOP (n) … (or OFFSET/FETCH)", "sqlite": "LIMIT n",
}

# Never removable — appended after any custom prompt.
SAFETY_RULES = """SAFETY RULES (non-negotiable):
- Output exactly ONE {dialect} SELECT statement. No markdown fences, no
  commentary, no trailing semicolon-separated statements.
- NEVER write INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, GRANT, CREATE,
  or SELECT … INTO.
- Use ONLY the tables and columns present in the context above.
- NEVER fabricate a query that returns a literal taken from the business
  documentation (e.g. `SELECT 22 AS days`). A query must READ the database.
  If the answer lives in the documentation and not in the tables, reply
  INSUFFICIENT_SCHEMA — the platform will answer it from the documents.
- If the question cannot be answered from that schema, reply with exactly:
  INSUFFICIENT_SCHEMA: <one line naming what is missing>
- Row limiting for this dialect: {limit_kw}."""

DEFAULT_RULES = """You write SQL for a {dialect} database.

GUIDELINES:
- Prefer explicit JOINs following the documented foreign-key relationships.
- When filtering on a text value, use the exact values listed in the
  business context (sample values). If unsure of the casing, compare
  case-insensitively — a user's phrasing rarely matches the stored casing.
- Aggregate when the question asks "how many", "total", "average"…
- Return only the columns the question asks for, plus the identifiers needed
  to make the answer readable (names rather than raw ids when available)."""


def build_system_rules(dialect: str, prompt_mode: str = "default",
                       custom_prompt: str = "") -> str:
    """The instruction block appended to EVERY generation prompt."""
    limit_kw = LIMIT_KEYWORD.get(dialect, "LIMIT n")
    base = (custom_prompt.strip() if prompt_mode == "custom" and custom_prompt.strip()
            else DEFAULT_RULES.format(dialect=dialect))
    safety = SAFETY_RULES.format(dialect=dialect, limit_kw=limit_kw)
    return f"{base}\n\n{safety}"


CORRECTION_TEMPLATE = """{question}

The SQL you produced was REJECTED by the validator.

Rejected SQL:
{sql}

Reason ({check}): {error}

Write a corrected {dialect} SELECT that fixes exactly this problem. Use only
tables and columns that exist in the context. Output SQL only."""


def build_correction_prompt(question: str, sql: str, check: str, error: str,
                            dialect: str) -> str:
    """The repair message — the reason the retry loop converges instead of
    guessing again. The validator's message is passed through verbatim."""
    return CORRECTION_TEMPLATE.format(question=question, sql=sql or "(none)",
                                      check=check, error=error, dialect=dialect)


ANSWER_TEMPLATE = """Question: {question}

SQL executed:
{sql}

Result: {row_count} row(s){truncated}
{preview}

Write a short, direct answer to the question in the user's language. State
the number when it is a count. Do not invent values that are not in the
result. Do not repeat the SQL."""


def build_answer_prompt(question: str, sql: str, row_count: int,
                        truncated: bool, preview: str) -> str:
    return ANSWER_TEMPLATE.format(
        question=question, sql=sql, row_count=row_count,
        truncated=" (truncated at the row limit)" if truncated else "",
        preview=preview)
