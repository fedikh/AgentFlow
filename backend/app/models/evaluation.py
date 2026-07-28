"""
Evaluation models — test datasets + experiment runs per RAG space.

EvalCase : one labeled test (question → ground-truth answer, expected source
           document/page, category/difficulty/language). Cases arrive by
           JSON upload (e.g. written by a domain expert) or Ragas generation.
EvalRun  : one experiment — the whole dataset executed against the space's
           CURRENT configuration. Stores per-case results (trace), aggregate
           metrics for the three families (retrieval / generation / system),
           the weighted overall score with its transparent breakdown, and a
           config snapshot so runs are comparable.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey

from app.database import Base


def _uid():
    return str(uuid.uuid4())


class EvalCase(Base):
    __tablename__ = "eval_cases"

    id = Column(String, primary_key=True, default=_uid)
    rag_space_id = Column(String, ForeignKey("rag_spaces.id", ondelete="CASCADE"),
                          nullable=False, index=True)

    question = Column(Text, nullable=False)
    expected_answer = Column(Text, nullable=True)      # ground truth (optional)
    expected_document = Column(String, nullable=True)  # file name (substring ok)
    expected_page = Column(Integer, nullable=True)
    category = Column(String, default="semantic")
    difficulty = Column(String, default="medium")      # easy | medium | hard
    language = Column(String, nullable=True)           # fr | en | …
    source = Column(String, default="manual")          # manual | upload | generated

    created_at = Column(DateTime, default=datetime.utcnow)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id = Column(String, primary_key=True, default=_uid)
    rag_space_id = Column(String, ForeignKey("rag_spaces.id", ondelete="CASCADE"),
                          nullable=False, index=True)

    config_summary = Column(Text, nullable=True)   # JSON: embedding/chunking/llm/retrieval/judge at run time
    metrics = Column(Text, nullable=True)          # JSON: aggregates + breakdown + per-category + recommendations
    results = Column(Text, nullable=True)          # JSON: per-case trace
    num_cases = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
