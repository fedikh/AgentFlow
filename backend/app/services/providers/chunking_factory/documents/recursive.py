"""Recursive char split over the document's text stream (tables/images intact)."""
from ..base import flatten_split, split_recursive, elements_of


def chunk(parsed, cfg):
    size = cfg.p("chunk_size", 512)
    overlap = cfg.p("chunk_overlap", 50)
    return flatten_split(elements_of(parsed),
                         lambda t: split_recursive(t, size, overlap), "recursive")
