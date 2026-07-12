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


def dedupe_paragraphs(text: str) -> tuple[str, int]:
    """Remove exact (normalized) duplicate paragraphs within a text block."""
    if not text:
        return "", 0
    paras = re.split(r"\n\s*\n", text)
    if len(paras) < 2:
        return text, 0
    seen = set()
    kept = []
    removed = 0
    for p in paras:
        k = _key(p)
        if not k:
            continue
        # Only dedupe paragraphs long enough to matter (avoid nuking short
        # legitimate repeats like "Yes" / a shared label).
        if len(k) > 25 and k in seen:
            removed += 1
            continue
        seen.add(k)
        kept.append(p)
    if removed:
        logger.info(f"[DEDUP] removed {removed} duplicate paragraph(s)")
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
