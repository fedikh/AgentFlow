"""Fixed-size — mechanical fixed-size character windows over the flattened
tree text (uniform sizes, ignores structure). Uses tree_stream so record
fields appear exactly once. Baseline; use record/node for structure."""
from ..base import fixed_chunks
from . import tree_stream


def chunk(parsed, cfg):
    size = cfg.p("chunk_size", 512)
    overlap = cfg.p("chunk_overlap", 50)
    return fixed_chunks(tree_stream(parsed), size, overlap, "fixed")
