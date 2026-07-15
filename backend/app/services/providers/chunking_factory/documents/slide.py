"""Slide-based (PPTX) — one chunk per slide. PPTX sets location.page = slide no."""
from ..base import group_by_page, elements_of


def chunk(parsed, cfg):
    return group_by_page(elements_of(parsed), "slide")
