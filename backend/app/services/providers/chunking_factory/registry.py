"""
Strategy catalog — the single source of truth for which strategies each format
category supports, their tunable parameters, and their UI metadata.

`STRATEGY_CATALOG[category]` → ordered list of strategy defs. Each def:
    {name, module, label, stars, recommended, best_for, pros, cons, params}
where each param is
    {key, label, type: "int"|"float"|"bool", default, min, max, step}
so the frontend can render the parameter inputs dynamically (no hardcoding).

Module path convention: chunking_factory.<category>.<module>, exposing chunk(parsed, cfg).
"""

# file extension / parser label → chunking category
FILE_CATEGORY = {
    # documents
    "pdf": "documents", "docx": "documents", "word": "documents",
    "pptx": "documents", "powerpoint": "documents",
    "txt": "documents", "text": "documents",
    "md": "documents", "markdown": "documents",
    # semi-structured
    "json": "semi_structured", "xml": "semi_structured",
    # tabular
    "csv": "tabular", "xlsx": "tabular", "xls": "tabular", "excel": "tabular",
    # web
    "html": "web", "htm": "web", "url": "web", "web": "web",
}


def category_for(file_type: str) -> str:
    return FILE_CATEGORY.get((file_type or "").lower(), "documents")


# ── reusable param definitions ──
_SIZE = {"key": "chunk_size", "label": "Chunk size (chars)", "type": "int",
         "default": 512, "min": 64, "max": 4000, "step": 32}
_OVERLAP = {"key": "chunk_overlap", "label": "Overlap (chars)", "type": "int",
            "default": 50, "min": 0, "max": 1000, "step": 10}
_MAXCHARS = {"key": "max_chars", "label": "Max size (chars)", "type": "int",
             "default": 1000, "min": 128, "max": 6000, "step": 64}
_MINCHARS = {"key": "min_chars", "label": "Merge under (chars)", "type": "int",
             "default": 120, "min": 0, "max": 2000, "step": 20}


STRATEGY_CATALOG = {
    "documents": [
        {"name": "recursive", "module": "recursive", "label": "Recursive", "stars": 5,
         "recommended": True, "best_for": ["pdf", "docx", "txt"],
         "pros": "Respects structure (paragraph→line→word); strong default",
         "cons": "Slightly slower than fixed",
         "params": [_SIZE, _OVERLAP]},
        {"name": "fixed", "module": "fixed", "label": "Fixed-size", "stars": 4,
         "best_for": ["benchmark", "baseline"],
         "pros": "Uniform, deterministic N-char windows — predictable baseline",
         "cons": "Cuts straight through headings, tables and sentences",
         "params": [_SIZE, _OVERLAP]},
        {"name": "sentence", "module": "sentence", "label": "Sentence", "stars": 4,
         "best_for": ["articles", "books"], "pros": "Never splits a sentence",
         "cons": "Uneven sizes",
         "params": [{**_MAXCHARS, "default": 800},
                    {"key": "overlap_sentences", "label": "Sentence overlap",
                     "type": "int", "default": 1, "min": 0, "max": 5, "step": 1}]},
        {"name": "paragraph", "module": "paragraph", "label": "Paragraph", "stars": 4,
         "best_for": ["articles", "docx"], "pros": "Keeps paragraphs whole",
         "cons": "Uneven sizes", "params": [{**_MAXCHARS, "default": 1000}]},
        {"name": "heading", "module": "heading", "label": "Section / heading", "stars": 5,
         "best_for": ["docx", "md", "manuals"],
         "pros": "One chunk per section — uses the document outline",
         "cons": "Needs real headings", "params": [{**_MAXCHARS, "default": 1500}]},
        {"name": "page", "module": "page", "label": "Page", "stars": 3,
         "best_for": ["pdf", "scanned"], "pros": "One page = one chunk",
         "cons": "Coarse", "params": []},
        {"name": "slide", "module": "slide", "label": "Slide", "stars": 5,
         "best_for": ["pptx"], "pros": "One slide = one chunk", "cons": "PPTX only",
         "params": []},
        {"name": "element", "module": "element", "label": "Element / Structure", "stars": 5,
         "best_for": ["md", "docling", "structured docs"],
         "pros": "Groups each section's elements (heading, text, code, table) into one coherent chunk — full structure preserved",
         "cons": "A large section makes a large chunk",
         "params": [{**_MAXCHARS, "default": 2500}]},
        {"name": "semantic", "module": "semantic", "label": "Semantic", "stars": 5,
         "best_for": ["pdf", "mixed topics"], "pros": "Splits on topic change",
         "cons": "Needs embeddings, slower",
         "params": [{"key": "threshold", "label": "Breakpoint percentile",
                     "type": "int", "default": 75, "min": 50, "max": 95, "step": 5},
                    {**_MAXCHARS, "default": 1200}]},
        {"name": "hierarchical", "module": "hierarchical", "label": "Hierarchical (parent-child)",
         "stars": 5, "best_for": ["advanced rag"],
         "pros": "Retrieve small child, expand with parent section",
         "cons": "Stores more chunks",
         "params": [{**_SIZE, "key": "child_size", "label": "Child size (chars)", "default": 400},
                    {"key": "parent_multiplier", "label": "Parent = child ×", "type": "int",
                     "default": 4, "min": 2, "max": 8, "step": 1}, _OVERLAP]},
        {"name": "llm", "module": "llm", "label": "LLM-based (OpenAI)", "stars": 5,
         "best_for": ["mixed topics", "narrative", "no headings"],
         "pros": "An OpenAI model finds meaning-based boundaries — one idea per chunk, never mid-sentence",
         "cons": "Needs an OpenAI key; slower + costs tokens (falls back to recursive without one)",
         "params": [{**_MAXCHARS, "key": "max_chars", "label": "Target size (chars)", "default": 1200}]},
    ],
    "semi_structured": [
        {"name": "node", "module": "node", "label": "Tree node", "stars": 5,
         "recommended": True, "best_for": ["json", "xml"],
         "pros": "One tree node = one chunk; small leaves merged",
         "cons": "Deep trees make many chunks", "params": [_MINCHARS]},
        {"name": "subtree", "module": "subtree", "label": "Subtree", "stars": 5,
         "best_for": ["json", "xml"],
         "pros": "A parent + its descendants up to a size — keeps records together",
         "cons": "Boundaries depend on tree shape", "params": [{**_MAXCHARS, "default": 1200}]},
        {"name": "recursive", "module": "recursive", "label": "Recursive", "stars": 3,
         "best_for": ["json", "xml"], "pros": "Simple size-based split of the flat text",
         "cons": "Ignores tree structure", "params": [_SIZE, _OVERLAP]},
        {"name": "fixed", "module": "fixed", "label": "Fixed-size", "stars": 2,
         "best_for": ["json", "xml"], "pros": "Deterministic", "cons": "Ignores structure",
         "params": [_SIZE, _OVERLAP]},
    ],
    "tabular": [
        {"name": "row", "module": "row", "label": "Row", "stars": 5,
         "recommended": True, "best_for": ["csv", "xlsx"],
         "pros": "One row + header context = one clean, citable unit",
         "cons": "Many chunks for big sheets",
         "params": [{"key": "include_header", "label": "Prefix header context",
                     "type": "bool", "default": True}]},
        {"name": "row_batch", "module": "row_batch", "label": "Row batch", "stars": 4,
         "best_for": ["csv", "xlsx"], "pros": "Fewer chunks; N rows share one chunk",
         "cons": "Coarser retrieval",
         "params": [{"key": "rows_per_chunk", "label": "Rows per chunk", "type": "int",
                     "default": 20, "min": 2, "max": 500, "step": 1},
                    {"key": "include_header", "label": "Prefix header context",
                     "type": "bool", "default": True}]},
        {"name": "table", "module": "table", "label": "Whole table", "stars": 3,
         "best_for": ["small tables"], "pros": "Table kept intact (split only if huge)",
         "cons": "Coarse for large tables", "params": [{**_MAXCHARS, "default": 2000}]},
        {"name": "sheet", "module": "sheet", "label": "Sheet", "stars": 3,
         "best_for": ["xlsx"], "pros": "One sheet (tables+charts+formulas) = one chunk",
         "cons": "Excel only; large", "params": []},
    ],
    "web": [
        {"name": "section", "module": "section", "label": "Section / heading", "stars": 5,
         "recommended": True, "best_for": ["html", "url"],
         "pros": "One chunk per page section — uses the h1–h6 outline",
         "cons": "Needs headings", "params": [{**_MAXCHARS, "default": 1500}]},
        {"name": "element", "module": "element", "label": "Element / Structure", "stars": 4,
         "best_for": ["html"],
         "pros": "Groups each section's blocks (heading, text, table, quote) into one coherent chunk",
         "cons": "A large section makes a large chunk",
         "params": [{**_MAXCHARS, "default": 2500}]},
        {"name": "recursive", "module": "recursive", "label": "Recursive", "stars": 4,
         "best_for": ["html", "url"], "pros": "Respects structure; strong default size split",
         "cons": "—", "params": [_SIZE, _OVERLAP]},
        {"name": "fixed", "module": "fixed", "label": "Fixed-size", "stars": 3,
         "best_for": ["html"], "pros": "Deterministic", "cons": "Can cut mid-sentence",
         "params": [_SIZE, _OVERLAP]},
        {"name": "llm", "module": "llm", "label": "LLM-based (OpenAI)", "stars": 5,
         "best_for": ["articles", "mixed topics"],
         "pros": "An OpenAI model finds meaning-based boundaries — one idea per chunk",
         "cons": "Needs an OpenAI key; slower + costs tokens (falls back to recursive without one)",
         "params": [{**_MAXCHARS, "key": "max_chars", "label": "Target size (chars)", "default": 1200}]},
    ],
}


# Agentic chunking is a MODE (not a per-format strategy) — its tunable params
# for the config UI. It runs the multi-agent OpenAI pipeline over any document.
AGENTIC_PARAMS = [
    {"key": "granularity", "label": "Granularity", "type": "select",
     "default": "balanced",
     "options": [{"value": "fine", "label": "Fine (smaller chunks)"},
                 {"value": "balanced", "label": "Balanced"},
                 {"value": "coarse", "label": "Coarse (larger chunks)"}]},
    {"key": "target_chars", "label": "Target size (chars)", "type": "int",
     "default": 1200, "min": 400, "max": 2500, "step": 50},
    {"key": "generate_metadata", "label": "Generate titles & keywords per chunk",
     "type": "bool", "default": True},
]

# The visual stages of the agentic pipeline (for the config UI diagram).
AGENTIC_STAGES = [
    {"key": "analyzer", "label": "Document Analyzer",
     "desc": "Understands the document — type, topics, structure"},
    {"key": "planner", "label": "Planning Agent",
     "desc": "Turns that into a concrete chunking plan"},
    {"key": "boundary", "label": "Semantic Boundary Detector",
     "desc": "Finds meaning-based split points"},
    {"key": "builder", "label": "Chunk Builder",
     "desc": "Assembles structure-preserving chunks"},
    {"key": "metadata", "label": "Metadata Generator",
     "desc": "Adds a title & keywords to each chunk"},
    {"key": "reviewer", "label": "Quality Reviewer",
     "desc": "Merges tiny chunks, splits oversized, cleans up"},
]


# Which strategies actually make sense per FILE TYPE (a subset of its category,
# in display order). E.g. "slide" is PPTX-only, "page" is PDF/scans, CSV has no
# "sheet". Order = the order shown in the UI.
ALLOWED_STRATEGIES = {
    # documents
    "pdf":      ["recursive", "fixed", "sentence", "paragraph", "heading", "page", "element", "semantic", "llm", "hierarchical"],
    "docx":     ["heading", "recursive", "fixed", "sentence", "paragraph", "element", "semantic", "llm", "hierarchical"],
    "pptx":     ["slide", "recursive", "fixed", "paragraph", "element", "semantic", "llm"],
    "txt":      ["recursive", "fixed", "sentence", "paragraph", "element", "semantic", "llm"],
    # Markdown, in ranked order (element/structure is the best fit for .md).
    "md":       ["element", "heading", "semantic", "llm", "recursive", "paragraph", "sentence", "fixed"],
    "markdown": ["element", "heading", "semantic", "llm", "recursive", "paragraph", "sentence", "fixed"],
    # semi-structured
    "json": ["node", "subtree", "recursive", "fixed"],
    "xml":  ["node", "subtree", "recursive", "fixed"],
    # tabular
    "csv":  ["row", "row_batch", "table"],
    "xlsx": ["row", "row_batch", "table", "sheet"],
    "xls":  ["row", "row_batch", "table", "sheet"],
    # web
    "html": ["section", "element", "recursive", "llm", "fixed"],
    "htm":  ["section", "element", "recursive", "llm", "fixed"],
    "url":  ["section", "element", "recursive", "llm", "fixed"],
}

# The recommended default per file type (badge + fallback).
RECOMMENDED_BY_TYPE = {
    "pdf": "recursive", "docx": "heading", "pptx": "slide", "txt": "recursive",
    "md": "element", "markdown": "element",
    "json": "node", "xml": "node",
    "csv": "row", "xlsx": "row", "xls": "row",
    "html": "section", "htm": "section", "url": "section",
}


def _by_name(category):
    return {s["name"]: s for s in STRATEGY_CATALOG.get(category, [])}


def allowed_names(file_type: str) -> list:
    """Strategy names valid for a file type (falls back to the whole category)."""
    ft = (file_type or "").lower()
    if ft in ALLOWED_STRATEGIES:
        return ALLOWED_STRATEGIES[ft]
    return [s["name"] for s in STRATEGY_CATALOG.get(category_for(ft), [])]


def strategies_for(file_type: str) -> list:
    """Ordered strategy defs valid for a file type (subset of its category)."""
    by = _by_name(category_for(file_type))
    out = [by[n] for n in allowed_names(file_type) if n in by]
    return out or STRATEGY_CATALOG.get(category_for(file_type), [])


def default_strategy(file_type: str) -> str:
    """The recommended strategy name for a file type."""
    ft = (file_type or "").lower()
    allowed = allowed_names(ft)
    rec = RECOMMENDED_BY_TYPE.get(ft)
    if rec and rec in allowed:
        return rec
    return allowed[0] if allowed else "recursive"


def strategy_def(file_type: str, name: str):
    """Resolve a strategy def valid for THIS file type, or None (enforces the
    per-file-type allow-list, so e.g. 'slide' is rejected for a PDF)."""
    name = (name or "").lower()
    if name not in allowed_names(file_type):
        return None
    return _by_name(category_for(file_type)).get(name)


def default_params(file_type: str, name: str) -> dict:
    d = strategy_def(file_type, name)
    if not d:
        return {}
    return {p["key"]: p["default"] for p in d.get("params", [])}
