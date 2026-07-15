"""
OCR Cleaner — detects and fixes OCR artifacts using pattern matching.

Fixes:
  1. Replacement chars (�)
  2. Garbage sequences (%%%%%, iiiiiii)
  3. Broken hyphenated words (docu-\\nment → document)
  4. True non-text noise (control characters)
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

# Control characters only (NUL..US and DEL), except \n \r \t which carry layout.
# IMPORTANT: we deliberately do NOT touch the 0x80-0xFF range — on a decoded
# string those are legitimate Latin-1 letters / French punctuation (é è à ç ù
# « » ° µ). The previous rule stripped runs of them and silently destroyed real
# French text. Mojibake is already repaired by ftfy (encoding stage, runs first).
_CTRL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+')


def fix_ocr(text: str) -> tuple[str, list[str]]:
    if not text:
        return "", []

    fixes = []

    # 1. Replacement characters
    count = text.count('�')
    if count > 0:
        text = text.replace('�', '')
        if count > 3:
            fixes.append(f"Removed {count} replacement chars (U+FFFD)")

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

    # 4. True non-text noise: control characters (see _CTRL).
    ctrl = _CTRL.findall(text)
    if ctrl:
        text = _CTRL.sub('', text)
        fixes.append(f"Removed {len(ctrl)} control sequence(s)")

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
