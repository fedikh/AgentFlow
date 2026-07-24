"""
Retrieval Engine — shared types.

Every retriever implements the same small interface (`BaseRetriever`), gets its
dependencies injected (session factory, space, config), and returns the same
`RetrievedChunk` shape — so the orchestrator can run any mix of them in
parallel and the fusion layer can merge results without caring where they came
from. Adding a retriever = one new class, zero changes to existing code.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# ── Query analysis result ────────────────────────────────────────────────────

@dataclass
class AnalyzedQuery:
    raw: str
    normalized: str = ""                 # lowercased, accent-stripped
    language: str = "en"                 # naive detection: "fr" | "en" | "other"
    intent: str = "semantic"             # semantic | keyword | exact_id | filename | metadata
    is_question: bool = False
    identifiers: list = field(default_factory=list)   # [{"value","kind"}] uuid/email/phone/number/code
    keywords: list = field(default_factory=list)      # salient tokens
    filenames: list = field(default_factory=list)     # names with an extension
    pages: list = field(default_factory=list)         # explicit "page N" references
    dates: list = field(default_factory=list)         # date-like strings
    expansions: list = field(default_factory=list)    # query variants (accent/sep-stripped…)
    rewritten: str = ""                  # LLM-rewritten query (transforms)
    hyde_text: str = ""                  # HyDE hypothetical answer (transforms)
    embedding: list | None = None        # filled by the orchestrator when dense runs


# ── Retrieved chunk (uniform across retrievers) ─────────────────────────────

@dataclass
class RetrievedChunk:
    chunk_id: int
    content: str
    document_id: str
    page: int = 1
    chunk_index: int = 0
    chunk_type: str = "text"
    image_path: str | None = None
    parent_index: int | None = None
    score: float = 0.0                   # retriever-native score (normalized in fusion)
    method: str = ""                     # which retriever produced it
    methods: set = field(default_factory=set)   # filled by fusion (all agreeing retrievers)

    def key(self):
        return self.chunk_id


# ── Retriever interface ──────────────────────────────────────────────────────

class BaseRetriever(ABC):
    """Common interface. Implementations must be side-effect free and safe to
    run in a worker thread with their OWN db session (injected factory)."""

    #: unique short name, used in strategies / logging / method tags
    name: str = "base"

    def __init__(self, session_factory, space, config):
        self.session_factory = session_factory
        self.space = space
        self.cfg = config

    @abstractmethod
    def retrieve(self, q: AnalyzedQuery, k: int) -> list[RetrievedChunk]:
        ...

    # Retrievers opt in/out per query (e.g. exact-match is pointless without
    # identifiers). The orchestrator consults this before scheduling.
    def applies_to(self, q: AnalyzedQuery) -> bool:
        return True
