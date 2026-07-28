"""LLM-based chunking — OpenAI predicts BOUNDARIES only (never touches text).

The model groups numbered paragraphs into topic-coherent chunks; the engine
rebuilds each chunk verbatim from the original paragraphs, validates the
grouping by paragraph ids, and adds overlap itself. The surrounding driver
keeps the document structure intact: headings become breadcrumbs, tables stay
whole, images become their own chunk. Falls back to recursive splitting when
no OpenAI key is available (see llm_client.make_llm_split)."""
from ..base import flatten_split, elements_of
from ..llm_client import make_llm_split


def chunk(parsed, cfg):
    access = cfg.p("_llm") or None
    max_chars = cfg.p("max_chars", 1200)
    overlap = cfg.p("chunk_overlap", 50)
    split_fn = make_llm_split(access, max_chars, overlap=overlap)
    return flatten_split(elements_of(parsed), split_fn, "llm")
