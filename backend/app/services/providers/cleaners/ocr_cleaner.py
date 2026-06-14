"""
OCR Cleaner — detects and fixes OCR artifacts using pattern matching.

Fixes:
  1. Replacement chars (�)
  2. Garbage sequences (%%%%%, iiiiiii)
  3. Broken hyphenated words (docu-\\nment → document)
  4. Garbled byte sequences
  5. Spaced-out text (s p a c e d → spaced)
  6. Excessive spaces from column detection
"""
import re
import logging

logger = logging.getLogger(__name__)

GARBAGE = [
    (r'[%]{4,}',  'Repeated %'),
    (r'[i]{6,}',  'Repeated i'),
    (r'[l]{6,}',  'Repeated l'),
    (r'[|]{4,}',  'Repeated |'),
    (r'[_]{10,}', 'Repeated _'),
    (r'[=]{10,}', 'Repeated ='),
    (r'[~]{5,}',  'Repeated ~'),
    (r'\.{6,}',   'Repeated dots'),
]


def fix_ocr(text: str) -> tuple[str, list[str]]:
    if not text:
        return "", []

    fixes = []

    # 1. Replacement characters
    count = text.count('\ufffd')
    if count > 0:
        text = text.replace('\ufffd', '')
        if count > 3:
            fixes.append(f"Removed {count} replacement chars (�)")

    # 2. Garbage patterns
    for pattern, desc in GARBAGE:
        matches = len(re.findall(pattern, text))
        if matches:
            text = re.sub(pattern, '', text)
            fixes.append(f"{desc} (×{matches})")

    # 3. Broken hyphenated words
    broken = len(re.findall(r'\w+-\n\w+', text))
    if broken:
        text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
        fixes.append(f"Rejoined {broken} hyphenated words")

    # 4. Garbled bytes
    garbled = re.findall(r'[\x80-\xff]{5,}', text)
    if garbled:
        for g in garbled:
            text = text.replace(g, '')
        fixes.append(f"Removed {len(garbled)} garbled sequences")

    # 5. Spaced-out text: "s p a c e d" → "spaced"
    spaced = re.findall(r'(?<!\w)(\w\s){5,}\w(?!\w)', text)
    if spaced:
        text = re.sub(r'(?<!\w)((?:\w\s){5,}\w)(?!\w)', lambda m: m.group(0).replace(' ', ''), text)
        fixes.append(f"Fixed {len(spaced)} spaced-out words")

    # 6. Triple+ spaces
    if '   ' in text:
        text = re.sub(r' {3,}', '  ', text)
        fixes.append("Collapsed excessive spaces")

    if fixes:
        logger.info(f"[OCR] {', '.join(fixes[:4])}")

    return text, fixes