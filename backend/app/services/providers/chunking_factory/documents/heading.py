"""Section/heading-based — one chunk per outline section (heading breadcrumb +
body), split only when a section exceeds max_chars. Tables/images become their
own chunk carrying the section breadcrumb; a heading never chunks on its own."""
from ..base import flatten_split, split_recursive, elements_of


def chunk(parsed, cfg):
    max_chars = cfg.p("max_chars", 1500)

    def keep_or_split(text):
        return [text] if len(text) <= max_chars else split_recursive(text, max_chars, 50)

    return flatten_split(elements_of(parsed), keep_or_split, "heading")
