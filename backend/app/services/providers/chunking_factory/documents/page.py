"""Page-based — one chunk per page (location.page)."""
from ..base import group_by_page, elements_of


def chunk(parsed, cfg):
    return group_by_page(elements_of(parsed), "page")
