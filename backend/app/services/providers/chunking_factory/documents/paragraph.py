"""Paragraph-based — packs whole paragraphs up to max_chars, never splitting a
paragraph. Section breadcrumb prepended, tables/images kept as their own chunk
(with the breadcrumb); a heading never chunks on its own."""
from ..base import flatten_split, pack_paragraphs, elements_of


def chunk(parsed, cfg):
    max_chars = cfg.p("max_chars", 1000)
    return flatten_split(elements_of(parsed),
                         lambda t: pack_paragraphs(t, max_chars), "paragraph")
