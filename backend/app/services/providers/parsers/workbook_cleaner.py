"""
Workbook cleaner — between raw Excel extraction and the final document.

Spreadsheet detectors over-produce: the same region can exist as a small
table, inside an overlapping "super-table", AND as a markdown cell_block;
layout artifacts (Column1 pseudo-headers, empty rows, 0-row title tables)
get emitted as data. One region must reach the chunker exactly ONCE, clean.

Rules:
  · drop 0-row and single-cell "tables" (titles/notes, not tables)
  · drop a table whose range strictly CONTAINS another detected table
    (re-detection of the whole region — the granular tables win)
  · drop cell_blocks that duplicate a kept table / a chart / a title header
  · keep one chart element per (sheet, title)
  · inside kept tables: drop empty rows, drop ColumnN pseudo-header rows,
    drop an all-empty title column
  · name tables from their real title ("Average travel"), not "Sheet!B4:E9"
  · rebuild the legacy sections from what actually survived
"""
from __future__ import annotations

import re

_GENERIC_HDR = re.compile(r"^(col|column)\s*_?\d+$|^unnamed", re.I)
_MACHINE_NAME = re.compile(
    r"^(table|sheet)\s*_?\d*$"                                    # Table1, Sheet_2
    r"|^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    r"|^[0-9a-f]{16,}$", re.I)


def _needs_rename(name: str) -> bool:
    """True when the parser-given table name is machine noise (empty, a range
    like 'Sheet1!B4:E9', 'Table3', a uuid) rather than a human title."""
    return (not name or "!" in name
            or bool(_GENERIC_HDR.match(name)) or bool(_MACHINE_NAME.match(name)))


def _range_tuple(rng):
    if rng in (None, "") or not str(rng).strip() or str(rng).lower() == "none":
        return None                      # range unknown ≠ single cell
    from openpyxl.utils import range_boundaries
    try:
        c0, r0, c1, r1 = range_boundaries(str(rng).split("!")[-1].replace("$", ""))
        if c0 is None and r0 is None:
            return None
        return (c0 or 1, r0 or 1, c1 or c0 or 1, r1 or r0 or 1)
    except Exception:
        return None


def _contains(a, b) -> bool:
    """True when range a strictly contains range b."""
    if a == b:
        return False
    return (a[0] <= b[0] and a[1] <= b[1] and a[2] >= b[2] and a[3] >= b[3]
            and (a[2] - a[0]) * (a[3] - a[1]) > (b[2] - b[0]) * (b[3] - b[1]))


def _is_pseudo_header_row(vals: dict) -> bool:
    non_empty = [str(v).strip() for v in vals.values() if v not in (None, "", " ")]
    return bool(non_empty) and all(re.fullmatch(r"Column\s*\d+", v) for v in non_empty)


def _friendly_table_name(content) -> str:
    """Form tables carry their merged-cell title as the FIRST column header
    ('Average travel', 'Purchase cost') — use it when it isn't generic."""
    cols = content.get("columns") or []
    if cols:
        first = str(cols[0].get("name") or "").strip()
        if first and not _GENERIC_HDR.match(first):
            return first
    return ""


def _clean_table_rows(content) -> None:
    rows = content.get("rows") or []
    cleaned = []
    for r in rows:
        vals = r.get("values") or {}
        # value-level artifact strip: 'Column1'/'Column2' placeholders inside
        # mixed rows ('Column1 | Buy a car | Rideshare') are styling noise
        for k, v in list(vals.items()):
            if v is not None and re.fullmatch(r"Column\s*\d+", str(v).strip()):
                vals[k] = None
        non_empty = {k: v for k, v in vals.items() if v not in (None, "", " ")}
        if not non_empty or _is_pseudo_header_row(vals):
            continue
        cleaned.append(r)
    cols = content.get("columns") or []
    if cols:
        first = cols[0].get("name")
        if all((r.get("values") or {}).get(first) in (None, "", " ") for r in cleaned):
            content["columns"] = cols[1:]
            for r in cleaned:
                (r.get("values") or {}).pop(first, None)
    for i, r in enumerate(cleaned, 1):
        r["index"] = i
    content["rows"] = cleaned


def render_rows(content) -> str:
    """Clean text rendering: generic colN labels omitted, empty values
    skipped — 'Average trips per day | 2 | min(s)' instead of
    'Average travel: None | col2: Average trips per day | col3: 2'."""
    headers = [c.get("name") for c in (content.get("columns") or [])]
    name = content.get("table_name") or ""
    show_name = bool(name) and not _GENERIC_HDR.match(name) and "!" not in name
    lines = [f"Table: {name}"] if show_name else []
    for r in (content.get("rows") or []):
        vals = r.get("values") or {}
        parts = []
        for h in headers:
            v = vals.get(h)
            if v in (None, "", " "):
                continue
            parts.append(str(v) if _GENERIC_HDR.match(str(h)) else f"{h}: {v}")
        if parts:
            lines.append(" | ".join(parts))
    return "\n".join(lines) if len(lines) > (1 if show_name else 0) else ""


def clean_workbook_elements(elements):
    """→ (kept_elements, rebuilt_chunk_sections)."""
    by_sheet_tables = {}
    for el in elements:
        if el.get("type") == "table":
            by_sheet_tables.setdefault(el["location"].get("sheet"), []).append(el)

    drop = set()

    for sheet, tables in by_sheet_tables.items():
        ranged = []
        for el in tables:
            rt = _range_tuple(el["location"].get("range") or "")
            c = el.get("content") or {}
            if not (c.get("rows") or []) or (rt and rt[0] == rt[2] and rt[1] == rt[3]):
                drop.add(el["id"])
                continue
            if rt:
                ranged.append((el, rt))
        for el, rt in ranged:
            if el["id"] in drop:
                continue
            for other, ot in ranged:
                if other["id"] != el["id"] and other["id"] not in drop and _contains(rt, ot):
                    drop.add(el["id"])
                    break

        # SLICE re-detections: a table whose cells are mostly covered by other
        # kept tables (e.g. a single-column strip C12:C19 duplicating the row
        # labels of B4:E11 + B14:E18). Its unique cells are footnotes that
        # already exist as calculation blocks — drop the slice.
        for el, rt in ranged:
            if el["id"] in drop:
                continue
            others = [ot for o, ot in ranged if o["id"] != el["id"] and o["id"] not in drop]
            if not others:
                continue
            cells = [(c, r) for c in range(rt[0], rt[2] + 1)
                     for r in range(rt[1], rt[3] + 1)]
            if len(cells) > 20000:              # safety: never enumerate huge grids
                continue
            covered = sum(1 for (c, r) in cells
                          if any(o[0] <= c <= o[2] and o[1] <= r <= o[3] for o in others))
            if covered / len(cells) >= 0.5:
                drop.add(el["id"])

    charts_by_sheet = {}
    seen_charts = set()
    for el in elements:
        if el.get("type") == "chart":
            key = (el["location"].get("sheet"), (el.get("content") or {}).get("title"))
            if key in seen_charts:
                drop.add(el["id"])
            else:
                seen_charts.add(key)
                charts_by_sheet.setdefault(key[0], []).append(el)

    # geometry beats block_type: detectors label the same cells 'table',
    # 'mixed' or 'text_block' inconsistently — compare cell ranges instead
    kept_ranges_by_sheet = {}
    for el in elements:
        if el.get("type") == "table" and el["id"] not in drop:
            rt = _range_tuple(el["location"].get("range") or "")
            if rt:
                kept_ranges_by_sheet.setdefault(el["location"].get("sheet"), []).append(rt)

    def _within(inner, outer):
        return (outer[0] <= inner[0] and outer[1] <= inner[1]
                and outer[2] >= inner[2] and outer[3] >= inner[3])

    for el in elements:
        if el.get("type") != "cell_block":
            continue
        bt = (el.get("content") or {}).get("block_type") or ""
        sheet = el["location"].get("sheet")
        rt = _range_tuple(el["location"].get("range") or "")
        t_ranges = kept_ranges_by_sheet.get(sheet, [])
        if bt == "header":
            drop.add(el["id"])                       # titles live in merged cells
        elif rt and any(_within(rt, t) for t in t_ranges):
            drop.add(el["id"])                       # same cells as a kept table
        elif rt and rt[1] == rt[3] and any(
                t[1] - 2 <= rt[1] < t[1] and rt[0] >= t[0] and rt[2] <= t[2] + 1
                for t in t_ranges):
            drop.add(el["id"])                       # 1-row title strip above a table
        elif bt == "chart_anchor" and charts_by_sheet.get(sheet):
            drop.add(el["id"])                       # the chart element wins

    kept = [el for el in elements if el["id"] not in drop]

    # merged-cell titles by sheet — fallback table names ('Average travel')
    # when the title cell didn't land in the table's header row
    merged_titles = {}
    for el in kept:
        if el.get("type") == "merged_cell":
            rt = _range_tuple((el.get("content") or {}).get("range") or "")
            val = (el.get("content") or {}).get("value")
            if rt and val not in (None, "", " "):
                merged_titles.setdefault(el["location"].get("sheet"), []).append((rt, str(val)))

    def _merged_title_for(sheet, rt):
        if not rt:
            return ""
        for mrt, val in merged_titles.get(sheet, []):
            # merged strip on the table's first row — or up to 2 rows above it
            # (title cell often sits just above the detected data range),
            # within the table's columns
            if rt[1] - 2 <= mrt[1] <= rt[1] and mrt[0] >= rt[0] and mrt[2] <= rt[2] + 1:
                return val
        return ""

    chunk_sections = []
    for el in kept:
        t = el.get("type")
        c = el.get("content") or {}
        sheet = (el.get("location") or {}).get("sheet") or ""
        if t == "table":
            _clean_table_rows(c)
            name = str(c.get("table_name") or "").strip()
            if _needs_rename(name):        # keep a human name the parser gave us
                name = (_friendly_table_name(c)
                        or _merged_title_for(sheet, _range_tuple(el["location"].get("range") or "")))
                if name:
                    c["table_name"] = name
            el["metadata"]["row_count"] = len(c.get("rows") or [])
            body = render_rows(c)
            if body:
                if name and name != sheet:
                    heading = f"{sheet} - {name}"
                else:
                    heading = name or f"{sheet}!{el['location'].get('range')}"
                chunk_sections.append((heading, body))
        elif t == "cell_block":
            txt = (c.get("text") or "").strip()
            if txt:
                chunk_sections.append((f"{sheet}!{c.get('cell_range')}", txt))
        elif t == "chart":
            if c.get("semantic_text"):
                chunk_sections.append((f"{sheet} - chart", c["semantic_text"]))

    for el in kept:
        rel = el.get("relationships") or {}
        if rel.get("children"):
            rel["children"] = [k for k in rel["children"] if k not in drop]

    return kept, chunk_sections
