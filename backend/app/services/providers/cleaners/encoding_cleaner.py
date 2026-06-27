"""
Encoding Cleaner — uses ftfy + chardet + unicodedata for encoding fixes.

ftfy fixes:
  â€™ → '     â€œ → "     Ã© → é     Ã§ → ç
  â€" → —     Â° → °     Ã¨ → è     Ã¢ → â

unicodedata fixes:
  ´ e → é     ` e → è     ˆ e → ê  (LaTeX/Docling split accents)

chardet detects the original encoding if ftfy can't fix it.
"""
import logging
import unicodedata
import re

logger = logging.getLogger(__name__)


def fix_encoding(text: str) -> tuple[str, list[str]]:
    if not text:
        return "", []

    fixes = []
    original = text

    # ── ftfy: primary encoding fixer ──
    try:
        import ftfy

        fixed = ftfy.fix_text(
            text,
            normalization="NFC",
            fix_entities=True,
            fix_character_width=True,
            fix_line_breaks=True,
            fix_surrogates=True,
            uncurl_quotes=False,
            fix_latin_ligatures=True,
        )

        if fixed != text:
            changes = sum(1 for a, b in zip(text, fixed) if a != b)
            fixes.append(f"ftfy fixed {changes} encoding issues")
            logger.info(f"[ENCODING] ftfy fixed {changes} chars")
            text = fixed

    except ImportError:
        logger.warning("[ENCODING] ftfy not installed — pip install ftfy")

    # ── unicodedata: fix LaTeX/Docling split accents ──
    # Remove spaces between accent marks and letters: ´ e → ´e
    before_accent = text
    text = re.sub(r'([`´ˆ¨¸˜̧̀́̂̈])\s+([a-zA-Z])', r'\1\2', text)
    # NFC normalization merges combining chars: ´e → é
    text = unicodedata.normalize("NFC", text)

    if text != before_accent:
        diff = len(before_accent) - len(text)
        fixes.append(f"Merged {diff} split accents (unicodedata NFC)")
        logger.info(f"[ENCODING] Merged split accents ({diff} chars)")

    # ── chardet: detect if text still has encoding issues ──
    try:
        import chardet

        sample = text[:2000].encode('utf-8', errors='replace')
        detected = chardet.detect(sample)
        enc = detected.get('encoding', 'utf-8')
        conf = detected.get('confidence', 0)

        if enc and enc.lower() not in ('utf-8', 'ascii') and conf > 0.7:
            try:
                re_encoded = sample.decode(enc, errors='replace')
                if re_encoded != text[:2000]:
                    fixes.append(f"chardet detected {enc} ({conf:.0%} confidence)")
            except Exception:
                pass

    except ImportError:
        pass

    return text, fixes