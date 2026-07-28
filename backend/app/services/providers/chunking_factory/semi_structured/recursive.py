"""Recursive size split over the flattened node text (ignores tree structure).
Uses tree_stream, so record fields appear exactly once."""
from ..base import flatten_split, split_recursive
from . import tree_stream


def chunk(parsed, cfg):
    size = cfg.p("chunk_size", 512)
    overlap = cfg.p("chunk_overlap", 50)
    return flatten_split(tree_stream(parsed),
                         lambda t: split_recursive(t, size, overlap), "recursive")
