"""Sentence-packing split — never splits a sentence."""
from ..base import flatten_split, split_sentences, elements_of


def chunk(parsed, cfg):
    max_chars = cfg.p("max_chars", 800)
    overlap = cfg.p("overlap_sentences", 1)
    return flatten_split(elements_of(parsed),
                         lambda t: split_sentences(t, max_chars, overlap), "sentence")
