"""Tree-node — one tree element = one chunk (semantic_text), tiny leaves merged."""
from ..base import element_chunks, elements_of


def chunk(parsed, cfg):
    return element_chunks(elements_of(parsed), "node", cfg.p("min_chars", 120))
