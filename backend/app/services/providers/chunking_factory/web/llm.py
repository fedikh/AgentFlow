"""LLM-based chunking for web pages — same engine as the documents strategy."""
from ..base import flatten_split, elements_of
from ..llm_client import make_llm_split


def chunk(parsed, cfg):
    access = cfg.p("_llm") or None
    max_chars = cfg.p("max_chars", 1200)
    split_fn = make_llm_split(access, max_chars)
    return flatten_split(elements_of(parsed), split_fn, "llm")
