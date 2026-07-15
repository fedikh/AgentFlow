"""Whole-table — one table element = one intact chunk (split only if oversize)."""
from ..base import elements_of, mk_chunk, table_text, split_recursive
from . import table_elements


def chunk(parsed, cfg):
    max_chars = cfg.p("max_chars", 2000)
    chunks, idx = [], 0
    for tbl in table_elements(elements_of(parsed)):
        txt = table_text(tbl)
        if not txt.strip():
            continue
        if len(txt) <= max_chars:
            chunks.append(mk_chunk(f"[TABLE]\n{txt}", 1, idx, "table", ctype="table"))
            idx += 1
        else:
            for piece in split_recursive(txt, max_chars, 0):
                chunks.append(mk_chunk(f"[TABLE]\n{piece}", 1, idx, "table", ctype="table"))
                idx += 1
    return chunks
