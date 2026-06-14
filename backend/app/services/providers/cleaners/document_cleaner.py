"""
Document Cleaner — removes structural noise from extracted documents.
Uses pattern matching to detect and remove:
  - Page numbers
  - Repeated headers/footers
  - Watermark text
  - Confidentiality notices
"""
import re
import logging
from collections import Counter

logger = logging.getLogger(__name__)

WATERMARKS = [
    r'(?i)^\s*(draft|brouillon)\s*$',
    r'(?i)^\s*(confidential|confidentiel)\s*$',
    r'(?i)^\s*do not (distribute|copy)\s*$',
    r'(?i)^\s*ne pas distribuer\s*$',
    r'(?i)^\s*(internal use only|usage interne)\s*$',
    r'(?i)^\s*proprietary\s*$',
    r'(?i)^\s*copyright\s+©?\s*\d{4}.*$',
    r'(?i)^\s*all rights reserved\s*$',
    r'(?i)^\s*tous droits r[ée]serv[ée]s\s*$',
]

PAGE_PATTERNS = [
    r'^\d{1,4}$',
    r'^(page|pg\.?|p\.?)\s*\d+(\s*(of|/|sur|de)\s*\d+)?$',
    r'^[-–—]\s*\d+\s*[-–—]$',
    r'^\d+\s*/\s*\d+$',
]


def remove_noise(text: str) -> tuple[str, list[str]]:
    if not text:
        return "", []

    fixes = []
    lines = text.split('\n')
    total = len([l for l in lines if l.strip()])

    # 1. Page numbers
    cleaned = []
    removed = 0
    for line in lines:
        s = line.strip()
        if s and _is_page_number(s):
            removed += 1
            continue
        cleaned.append(line)
    if removed:
        fixes.append(f"Removed {removed} page numbers")
    lines = cleaned

    # 2. Watermarks
    cleaned = []
    removed = 0
    for line in lines:
        s = line.strip()
        if s and _is_watermark(s):
            removed += 1
            continue
        cleaned.append(line)
    if removed:
        fixes.append(f"Removed {removed} watermarks")
    lines = cleaned

    # 3. Repeated headers/footers
    if total > 20:
        counts = Counter(l.strip() for l in lines if l.strip())
        threshold = max(3, total // 15)
        repeated = set()

        for text_line, count in counts.items():
            if count >= threshold and 1 < len(text_line) < 120:
                if not _is_content(text_line):
                    repeated.add(text_line)

        if repeated:
            cleaned = []
            removed = 0
            for line in lines:
                if line.strip() in repeated:
                    removed += 1
                    continue
                cleaned.append(line)
            if removed:
                patterns = [f'"{r[:40]}"' for r in list(repeated)[:3]]
                fixes.append(f"Removed {removed} repeated lines: {', '.join(patterns)}")
            lines = cleaned

    if fixes:
        logger.info(f"[DOCUMENT] {'; '.join(fixes)}")

    return '\n'.join(lines), fixes


def _is_page_number(line):
    if len(line) > 30: return False
    return any(re.match(p, line, re.IGNORECASE) for p in PAGE_PATTERNS)

def _is_watermark(line):
    return any(re.match(p, line) for p in WATERMARKS)

def _is_content(line):
    if re.match(r'^[-•·▪▸►]\s', line): return True
    if len(line) < 3: return True
    if len(line.split()) > 10: return True
    return False