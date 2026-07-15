"""Element / Structure-Based — one coherent chunk per section: heading + its
blocks (paragraphs, lists, code, tables, quotes) kept together, preserving the
page structure."""
from ..base import structure_chunks, elements_of


def chunk(parsed, cfg):
    return structure_chunks(elements_of(parsed), "element", cfg.p("max_chars", 2500))
