"""
Data Agent evaluation models — test datasets + experiment runs per data agent
(the eval_cases / eval_runs pattern, keyed on data_sources).

DataEvalCase : one labeled test (question → GOLD SQL). The gold SQL is the
               ground truth: at run time both it and the agent's generated SQL
               are executed (read-only, validated) and their result sets
               compared — execution accuracy. category="insufficient" cases
               have no gold SQL: the right behaviour is an honest refusal.
DataEvalRun  : one experiment — every VERIFIED case executed against the
               agent's CURRENT configuration. Stores the per-case trace, the
               aggregate metric families and a sanitized config snapshot so
               runs are comparable.
"""
import uuid
from datetime import datetime

from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer,
                        String, Text)

from app.database import Base


def _uid():
    return str(uuid.uuid4())


class DataEvalCase(Base):
    __tablename__ = "data_eval_cases"

    id = Column(String, primary_key=True, default=_uid)
    data_source_id = Column(String, ForeignKey("data_sources.id", ondelete="CASCADE"),
                            nullable=False, index=True)

    question = Column(Text, nullable=False)
    gold_sql = Column(Text, nullable=True)          # null only for category="insufficient"
    expected_answer = Column(Text, nullable=True)   # optional NL ground truth (judge)
    category = Column(String, default="filter")     # aggregation|join|filter|date|ranking|grouping|subquery|insufficient
    difficulty = Column(String, default="medium")   # easy | medium | hard
    language = Column(String, nullable=True)
    source = Column(String, default="manual")       # manual | examples | upload | generated
    verified = Column(Boolean, default=True)        # generated cases start False
    gold_note = Column(Text, nullable=True)         # last gold-SQL validation error

    created_at = Column(DateTime, default=datetime.utcnow)


class DataEvalRun(Base):
    __tablename__ = "data_eval_runs"

    id = Column(String, primary_key=True, default=_uid)
    data_source_id = Column(String, ForeignKey("data_sources.id", ondelete="CASCADE"),
                            nullable=False, index=True)

    config_summary = Column(Text, nullable=True)   # JSON: sanitized agent config at run time
    metrics = Column(Text, nullable=True)          # JSON: families + by_category + recommendations
    results = Column(Text, nullable=True)          # JSON: per-case trace
    num_cases = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
