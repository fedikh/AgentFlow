"""Tabular chunking strategies (csv, xlsx, xls) + shared row helpers."""


def table_elements(elements):
    return [e for e in elements if e.get("type") == "table"]


def headers_of(content):
    return content.get("headers") or [c.get("name") for c in (content.get("columns") or [])]


def row_values(r):
    return r.get("values") if isinstance(r, dict) and "values" in r else r


def row_line(headers, vals):
    if headers:
        return " | ".join(f"{h}: {vals.get(h, '')}" for h in headers)
    return " | ".join(f"{k}: {v}" for k, v in vals.items())
