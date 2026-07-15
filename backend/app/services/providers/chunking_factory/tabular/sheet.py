"""Sheet-based — one chunk per sheet (its tables + charts + formulas). For a CSV
(single, sheet-less table) this yields one chunk for the whole file."""
from ..base import elements_of, mk_chunk, text_of, table_text

_SKIP = {"workbook", "cell_block", "merged_cell"}   # noise / duplicates table data


def chunk(parsed, cfg):
    groups, order = {}, []

    def bucket(key):
        if key not in groups:
            groups[key] = []
            order.append(key)
        return groups[key]

    for e in elements_of(parsed):
        t = e.get("type")
        if t in _SKIP:
            continue
        sheet = (e.get("location") or {}).get("sheet")
        if t == "sheet":
            key = sheet or e.get("id")
            bucket(key).insert(0, text_of(e))       # sheet summary leads the chunk
            continue
        key = sheet or "_"
        txt = table_text(e) if t == "table" else text_of(e)
        if txt:
            bucket(key).append(txt)

    chunks, idx = [], 0
    for key in order:
        parts = [p for p in groups[key] if p]
        if parts:
            chunks.append(mk_chunk("\n\n".join(parts), 1, idx, "sheet")); idx += 1
    return chunks
