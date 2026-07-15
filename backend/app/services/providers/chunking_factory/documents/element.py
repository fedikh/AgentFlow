"""Element / Structure-Based — uses the parsed elements to build ONE coherent
chunk per section: heading + its paragraphs, lists, code blocks and tables kept
together, preserving the document hierarchy. Best for structured parsers."""
from ..base import structure_chunks, elements_of


def chunk(parsed, cfg):
    return structure_chunks(elements_of(parsed), "element", cfg.p("max_chars", 2500))
