"""LLM-based chunking — OpenAI decides passage boundaries.

Splits each section's text into semantically coherent passages using an OpenAI
model (never mid-sentence, one idea per chunk), while the surrounding driver
keeps the document structure intact: headings become breadcrumbs, tables stay
whole, images become their own chunk. Falls back to recursive splitting when no
OpenAI key is available (see llm_client.make_llm_split)."""
from ..base import flatten_split, elements_of
from ..llm_client import make_llm_split


def chunk(parsed, cfg):
    access = cfg.p("_llm") or None
    max_chars = cfg.p("max_chars", 1200)
    split_fn = make_llm_split(access, max_chars)
    return flatten_split(elements_of(parsed), split_fn, "llm")
