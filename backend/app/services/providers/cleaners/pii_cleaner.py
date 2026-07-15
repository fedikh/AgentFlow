"""
PII Cleaner — detect (and optionally redact) personally identifiable info.

Non-destructive by default: detect() only COUNTS PII and returns a report that
the pipeline stores in metadata. Redaction (replacing values with a placeholder)
is opt-in via CLEAN_REDACT_PII, because a knowledge base often legitimately
contains emails/phones you don't want to destroy.

Pure regex — no external packages, so it's fast and dependency-free.
"""
import re
import logging

logger = logging.getLogger(__name__)

# Order matters: match the most specific patterns first so an email isn't
# partially eaten by the phone matcher, etc.
PATTERNS = [
    ("email",       re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')),
    # 16-digit card, grouped (4×4) or solid — not a loose 13-16 run (which hit IDs).
    ("credit_card", re.compile(r'\b(?:\d{4}[ -]){3}\d{4}\b|\b\d{16}\b')),
    ("iban",        re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b')),
    ("ssn",         re.compile(r'\b\d{3}-\d{2}-\d{4}\b')),
    ("ipv4",        re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')),
    ("phone",       re.compile(r'(?<!\d)(?:\+?\d{1,3}[ .-]?)?(?:\(?\d{2,4}\)?[ .-]?){2,4}\d{2,4}(?!\d)')),
]

PLACEHOLDER = "[{}]"

# A bare date like "12 03 2024" or "12/03/24" matches the phone pattern; reject it.
_DATE = re.compile(r'^\d{1,2}[ ./-]\d{1,2}[ ./-]\d{2,4}$')


def _valid(name: str, match: str) -> bool:
    """Reject the common false positives before counting/redacting."""
    if name == "phone":
        digits = re.sub(r'\D', '', match)
        if not (7 <= len(digits) <= 15):   # real phone numbers are 7-15 digits
            return False
        if _DATE.match(match.strip()):      # a date, not a phone number
            return False
    return True


def detect_pii(text: str) -> dict:
    """Return {pii_type: count} for the text (no mutation)."""
    if not text:
        return {}
    found = {}
    for name, rx in PATTERNS:
        n = sum(1 for m in rx.findall(text) if _valid(name, m))
        if n:
            found[name] = found.get(name, 0) + n
    return found


def redact_pii(text: str) -> tuple[str, dict]:
    """Replace PII with typed placeholders, e.g. '[EMAIL]'. Returns (text, counts)."""
    if not text:
        return "", {}
    counts = {}
    for name, rx in PATTERNS:
        def _sub(m, _name=name):
            if not _valid(_name, m.group(0)):
                return m.group(0)
            counts[_name] = counts.get(_name, 0) + 1
            return PLACEHOLDER.format(_name.upper())
        text = rx.sub(_sub, text)
    if counts:
        logger.info(f"[PII] redacted {counts}")
    return text, counts
