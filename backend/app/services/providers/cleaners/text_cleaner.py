"""
Text Cleaner — uses clean-text + unidecode for comprehensive normalization.

clean-text handles:
  - Unicode normalization
  - Whitespace collapsing
  - Control character removal
  - Smart quote normalization

unidecode handles:
  - Transliteration for search (café → cafe)
  - Stored separately as search_text in metadata
"""
import re
import logging

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> tuple[str, list[str]]:
    if not text:
        return "", []

    fixes = []
    original_len = len(text)

    # ── clean-text: primary text normalizer ──
    try:
        from cleantext import clean

        cleaned = clean(
            text,
            fix_unicode=True,           # fix Unicode issues
            to_ascii=False,             # keep accented chars (important for French)
            lower=False,                # keep original case
            no_line_breaks=False,       # keep paragraph structure
            no_urls=False,              # keep URLs (might be content)
            no_emails=False,            # keep emails (might be content)
            no_phone_numbers=False,     # keep phone numbers
            no_numbers=False,           # keep numbers
            no_digits=False,            # keep digits
            no_currency_symbols=False,  # keep currency
            no_punct=False,             # keep punctuation
            no_emoji=True,              # remove emojis (noise in documents)
            replace_with_punct="",
            replace_with_url="",
            replace_with_email="",
            replace_with_phone_number="",
            replace_with_number="",
            replace_with_digit="",
            replace_with_currency_symbol="",
        )

        if cleaned != text:
            diff = len(text) - len(cleaned)
            fixes.append(f"clean-text normalized ({diff} chars)")
            text = cleaned

    except ImportError:
        logger.warning("[TEXT] clean-text not installed — pip install clean-text")

    # ── Additional normalizations ──

    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Collapse multiple spaces (preserve newlines)
    before = len(text)
    text = re.sub(r'[^\S\n]+', ' ', text)
    if len(text) != before:
        fixes.append("Collapsed multiple spaces")

    # Strip trailing whitespace per line
    text = '\n'.join(line.rstrip() for line in text.split('\n'))

    # Collapse 3+ blank lines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Strip leading/trailing
    text = text.strip()

    total_diff = original_len - len(text)
    if total_diff > 0 and not fixes:
        fixes.append(f"Removed {total_diff} chars whitespace")

    if fixes:
        logger.info(f"[TEXT] {', '.join(fixes)}")

    return text, fixes


def get_search_text(text: str) -> str:
    """
    Generate ASCII-only version for search indexing.
    Uses unidecode: café → cafe, naïve → naive, Ã → A

    Store this alongside the original for accent-insensitive search.
    """
    try:
        from unidecode import unidecode
        return unidecode(text)
    except ImportError:
        logger.warning("[TEXT] unidecode not installed — pip install unidecode")
        return text