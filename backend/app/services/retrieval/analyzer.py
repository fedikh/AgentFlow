"""
Query Analyzer — classifies every query BEFORE retrieval.

Detects language, intent, identifiers (registration/invoice numbers, UUIDs,
emails, phones, employee ids…), filenames, page references, dates and salient
keywords, and produces deterministic query expansions. The orchestrator maps
the resulting intent to a retrieval strategy:

    "2300114"                    → exact_id   → Exact + BM25
    "N° inscription 2300114"     → exact_id   → Exact + BM25 (+ metadata)
    "Eya Ben Fredj" / "SOFRECOM" → keyword    → BM25 + Dense (hybrid)
    "rapport_2025.pdf"           → filename   → Metadata + BM25
    "page 12 of the policy"      → metadata   → Metadata + Dense
    "Explain the leave policy"   → semantic   → Dense + BM25 (+ reranker)

Everything here is dependency-free and pure — easy to unit test.
"""
from __future__ import annotations

import re
import unicodedata

from .types import AnalyzedQuery

# ── regexes ──────────────────────────────────────────────────────────────────
RE_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
RE_PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{6,}\d(?!\w)")
RE_NUMBER = re.compile(r"(?<![\w./-])\d{4,}(?![\w./-])")          # 2300114, invoice/employee ids
RE_SEPNUM = re.compile(r"(?<![\w.])\d{2,}(?:[-.\s]\d{2,})+(?![\w.])")  # 23-00-114, 12 34 567
RE_CODE = re.compile(r"\b(?=[\w-]*\d)(?=[\w-]*[A-Za-z])[A-Za-z0-9][A-Za-z0-9_-]{4,}\b")  # INV-2024-88, AB12CD
RE_FILENAME = re.compile(
    r"\b[\w.-]+\.(pdf|docx?|pptx?|xlsx?|csv|txt|md|json|xml|html?)\b", re.I)
RE_DATE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|20\d{2})\b")
RE_PAGE = re.compile(r"\bpage\s*(\d{1,4})\b", re.I)

QUESTION_WORDS = {
    "what", "why", "how", "when", "where", "who", "which", "explain", "describe",
    "compare", "summarize", "can", "does", "is", "are", "should",
    "quoi", "pourquoi", "comment", "quand", "où", "qui", "quel", "quelle",
    "quels", "quelles", "explique", "expliquer", "décris", "résume", "est-ce",
}
FR_HINTS = {"le", "la", "les", "des", "une", "un", "du", "de", "et", "est",
            "pour", "avec", "dans", "sur", "quelle", "quel", "comment", "pourquoi",
            "politique", "congé", "congés", "numéro", "inscription", "fiche"}
EN_HINTS = {"the", "a", "an", "of", "and", "is", "for", "with", "in", "on",
            "what", "how", "why", "policy", "leave", "number", "report"}

# words that accompany an identifier but aren't content ("N° inscription 2300114")
ID_CONTEXT_WORDS = {
    "n°", "no", "num", "numero", "numéro", "id", "ref", "réf", "reference",
    "référence", "inscription", "invoice", "facture", "matricule", "employee",
    "employé", "serial", "série", "code", "dossier", "contrat", "contract",
}

STOPWORDS = FR_HINTS | EN_HINTS | {"me", "my", "please", "svp", "stp", "give", "show", "find"}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _detect_language(tokens: list) -> str:
    t = set(tokens)
    fr = len(t & FR_HINTS)
    en = len(t & EN_HINTS)
    if fr == en == 0:
        return "other"
    return "fr" if fr >= en else "en"


def analyze(raw: str) -> AnalyzedQuery:
    q = AnalyzedQuery(raw=raw or "")
    text = (raw or "").strip()
    if not text:
        return q

    norm = strip_accents(text.lower())
    q.normalized = norm
    tokens = re.findall(r"[\w°@.+-]+", norm)
    q.is_question = text.endswith("?") or (tokens and tokens[0] in QUESTION_WORDS)
    q.language = _detect_language(tokens)

    # ── identifiers ──
    seen = set()

    def add_id(value, kind):
        v = value.strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            q.identifiers.append({"value": v, "kind": kind})

    for m in RE_UUID.findall(text):
        add_id(m, "uuid")
    for m in RE_EMAIL.findall(text):
        add_id(m, "email")
    for m in RE_FILENAME.finditer(text):
        q.filenames.append(m.group(0))
    for m in RE_PAGE.finditer(text):
        q.pages.append(int(m.group(1)))
    for m in RE_DATE.findall(text):
        q.dates.append(m if isinstance(m, str) else m[0])
    # phones only when they don't collide with plain numbers already captured
    for m in RE_PHONE.findall(text):
        digits = re.sub(r"\D", "", m)
        if len(digits) >= 8:
            add_id(m.strip(), "phone")
    for m in RE_NUMBER.findall(text):
        # years alone are dates, not identifiers
        if not (len(m) == 4 and m.startswith(("19", "20"))):
            add_id(m, "number")
    for m in RE_SEPNUM.findall(text):
        if len(re.sub(r"\D", "", m)) >= 4:
            add_id(m.strip(), "number")
    for m in RE_CODE.findall(text):
        if m.lower() not in {f.lower() for f in q.filenames}:
            add_id(m, "code")

    # ── keywords (salient tokens, minus stopwords / id-context words) ──
    q.keywords = [
        t for t in tokens
        if len(t) > 2 and t not in STOPWORDS and t not in ID_CONTEXT_WORDS
        and not t.isdigit()
    ]

    # ── intent ──
    # "meaningful" tokens = content words that are NOT part of an identifier,
    # not id-context ("n°", "invoice"…), not stopwords, not bare digits.
    id_values = " ".join(i["value"].lower() for i in q.identifiers)
    meaningful = [
        t for t in tokens
        if len(t) > 2 and t not in ID_CONTEXT_WORDS and t not in STOPWORDS
        and not t.replace("-", "").replace(".", "").isdigit()
        and t not in id_values
    ]
    if q.filenames and len(tokens) <= 6:
        q.intent = "filename"
    elif q.identifiers and not meaningful:
        q.intent = "exact_id"           # nothing but the identifier (+ context words)
    elif q.pages and len(tokens) <= 8:
        q.intent = "metadata"
    elif q.identifiers:
        q.intent = "hybrid_id"          # identifier + real words → exact AND semantic
    elif q.is_question or len(tokens) >= 6:
        q.intent = "semantic"
    else:
        q.intent = "keyword"            # short entity queries: names, companies…

    # ── deterministic expansions ──
    exp = set()
    if norm != text.lower():
        exp.add(norm)                                     # accent-stripped
    for ident in q.identifiers:
        v = ident["value"]
        bare = re.sub(r"[\s.-]", "", v)
        if bare != v:
            exp.add(bare)                                 # "23 00 114" → "2300114"
    if q.intent in ("keyword", "hybrid_id") and q.keywords:
        exp.add(" ".join(q.keywords))                     # entity-only variant
    q.expansions = [e for e in exp if e and e != text.lower()]

    return q
