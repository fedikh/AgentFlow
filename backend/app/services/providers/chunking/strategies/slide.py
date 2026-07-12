"""Slide-based chunking — for PPTX, one slide = one chunk. Slides map to pages
in the parsed document, so this is page-based chunking under a PPTX-friendly name.
"""
from . import page


def chunk(blocks, opts):
    return page.chunk(blocks, opts)
