"""Retrieval Engine — shared types."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Query:
    """The query as it flows through the pipeline."""
    raw: str
    cleaned: str = ""                    # transform output (rewrite / spell / noise)
    variants: list = field(default_factory=list)   # multi-query expansions
    embedding: list | None = None        # filled by the orchestrator (vector mode)

    @property
    def text(self) -> str:
        """The best available form of the query."""
        return self.cleaned or self.raw


@dataclass
class RetrievedChunk:
    """Uniform result shape across retrievers — fusion merges them by id."""
    chunk_id: str
    content: str
    document_id: str
    page: int = 1
    chunk_index: int = 0
    chunk_type: str = "text"
    image_path: str | None = None
    score: float = 0.0                   # retriever-native score
    method: str = ""                     # which retriever produced it
    methods: set = field(default_factory=set)   # all agreeing retrievers


class BaseRetriever(ABC):
    """Common interface. Implementations run in worker threads with their
    OWN db session (injected factory) — side-effect free."""

    name: str = "base"

    def __init__(self, session_factory, space, config):
        self.session_factory = session_factory
        self.space = space
        self.cfg = config

    @abstractmethod
    def retrieve(self, q: Query, k: int) -> list[RetrievedChunk]:
        ...
