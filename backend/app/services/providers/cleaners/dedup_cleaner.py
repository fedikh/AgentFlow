"""
Dedup Cleaner — removes duplicate content so the same text isn't embedded twice.

Two levels:
  * dedupe_paragraphs(text)  → drop repeated paragraphs inside one block
  * dedupe_sections(sections) → drop whole sections whose (heading+content)
                                already appeared (e.g. repeated boilerplate)

Matching is done on a normalized key (lowercased, whitespace-collapsed) so
cosmetic differences don't defeat it. First occurrence is always kept.
"""
import re
import logging

logger = logging.getLogger(__name__)

_WS = re.compile(r"\s+")


def _key(text: str) -> str:
    return _WS.sub(" ", (text or "").strip().lower())


def _collapse_adjacent_lines(text: str) -> tuple[str, int]:
    """Collapse runs of identical *consecutive* lines (len > 25).

    Extraction + noise removal frequently leave the same sentence twice on
    adjacent lines (e.g. a repeated slide/page header once its page number is
    stripped). Paragraph dedup misses these because they aren't separated by a
    blank line. Only exact, back-to-back, long lines are collapsed, so genuine
    short repeats (a list of "Yes") are left alone.
    """
    lines = text.split("\n")
    out = []
    removed = 0
    prev = None
    for ln in lines:
        k = _key(ln)
        if not k:
            out.append(ln)
            prev = None            # a blank line breaks the "adjacent" run
            continue
        if len(k) > 25 and k == prev:
            removed += 1
            continue
        out.append(ln)
        prev = k
    return "\n".join(out), removed


def dedupe_paragraphs(text: str) -> tuple[str, int]:
    """Remove duplicate content within a text block, at two granularities:
    consecutive identical lines, then blank-line-separated paragraphs."""
    if not text:
        return "", 0

    # 1) consecutive identical lines (survive paragraph dedup otherwise)
    text, line_removed = _collapse_adjacent_lines(text)

    # 2) blank-line-separated paragraphs
    paras = re.split(r"\n\s*\n", text)
    seen = set()
    kept = []
    para_removed = 0
    for p in paras:
        k = _key(p)
        if not k:
            continue
        # Only dedupe paragraphs long enough to matter (avoid nuking short
        # legitimate repeats like "Yes" / a shared label).
        if len(k) > 25 and k in seen:
            para_removed += 1
            continue
        seen.add(k)
        kept.append(p)

    removed = line_removed + para_removed
    if removed:
        logger.info(f"[DEDUP] removed {para_removed} duplicate paragraph(s), "
                    f"{line_removed} duplicate line(s)")
    return "\n\n".join(kept), removed


def dedupe_sections(sections: list[dict]) -> tuple[list[dict], int]:
    """Drop sections whose normalized (heading + content) was already seen."""
    if not sections:
        return sections, 0
    seen = set()
    kept = []
    removed = 0
    for sec in sections:
        k = _key((sec.get("heading", "") or "") + " " + (sec.get("content", "") or ""))
        if not k:
            kept.append(sec)
            continue
        if len(k) > 25 and k in seen:
            removed += 1
            continue
        seen.add(k)
        kept.append(sec)
    if removed:
        logger.info(f"[DEDUP] removed {removed} duplicate section(s)")
    return kept, removed
