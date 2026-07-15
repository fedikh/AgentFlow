"""Fixed-size — TRUE mechanical fixed-size character windows over the whole
document (uniform sizes, cuts straight through sections/tables). The predictable,
structure-agnostic baseline; use recursive/heading for structure-aware chunks."""
from ..base import fixed_chunks, elements_of


def chunk(parsed, cfg):
    size = cfg.p("chunk_size", 512)
    overlap = cfg.p("chunk_overlap", 50)
    return fixed_chunks(elements_of(parsed), size, overlap, "fixed")
