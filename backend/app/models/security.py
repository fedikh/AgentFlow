"""
Security evaluation models — the second, symmetric evaluation engine.

    security_cases    the FROZEN attack corpus (seeded once; never generated at
                      scan time, so before/after runs stay comparable).
    security_runs     one campaign against a space's real pipeline, with an
                      immutable config_snapshot (what was tested) + the weighted
                      robustness score and the count of critical failures.
    security_results  one case in a campaign: the agent response, the retrieved
                      chunk ids, the verdict (BLOCKED/LEAKED/PARTIAL), what
                      decided it (rule/judge), the proving evidence, latency.

Conventions (same as the rest of the platform): String UUID PKs, plain String
enums (new values never need a migration), JSON stored as Text; tables created
by create_all (the project does not use Alembic).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (Boolean, Column, DateTime, Float, ForeignKey, Index,
                        Integer, String, Text)

from app.database import Base

# ── the attack categories ──
CATEGORIES = (
    "direct_injection",       # ignore instructions / execute injected commands
    "jailbreak",              # role-play / DAN to drop guardrails
    "system_prompt_leak",     # reveal the hidden instructions verbatim
    "out_of_scope",           # answer off-topic questions it should decline
    "source_hallucination",   # cite a source that was never retrieved
)
SEVERITIES = ("critical", "high", "medium", "low")
DETECTION_METHODS = ("rule", "judge", "both")
VERDICTS = ("BLOCKED", "LEAKED", "PARTIAL")

# criticality weights for the robustness score
SEVERITY_WEIGHTS = {"critical": 5, "high": 3, "medium": 2, "low": 1}


def _now():
    return datetime.now(timezone.utc)


def _uid():
    return str(uuid.uuid4())


class SecurityCase(Base):
    __tablename__ = "security_cases"

    id                = Column(String, primary_key=True, default=_uid)
    category          = Column(String, nullable=False)   # CATEGORIES
    attack_prompt     = Column(Text, nullable=False)     # sent to the agent
    expected_behavior = Column(Text, nullable=False)     # what a safe agent does
    severity          = Column(String, default="high")   # SEVERITIES
    detection_method  = Column(String, default="both")   # DETECTION_METHODS
    rule_config       = Column(Text, nullable=True)      # JSON: rule params
    source            = Column(String, default="manual") # manual | deepteam
    lang              = Column(String, default="en")     # en | fr
    is_active         = Column(Boolean, default=True)    # retire without deleting
    created_at        = Column(DateTime, default=_now)


class SecurityRun(Base):
    __tablename__ = "security_runs"

    id               = Column(String, primary_key=True, default=_uid)
    space_id         = Column(String, ForeignKey("rag_spaces.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    config_snapshot  = Column(Text, nullable=True)       # JSON: exact config tested
    categories       = Column(Text, nullable=True)       # JSON: selected categories
    judge_model      = Column(String, nullable=True)     # resolved judge label
    status           = Column(String, default="running") # running|done|error
    robustness_score = Column(Float, nullable=True)      # 0-100, severity-weighted
    critical_failures = Column(Integer, default=0)
    metrics          = Column(Text, nullable=True)       # JSON: per-category ASR + counts
    error            = Column(String, nullable=True)
    started_at       = Column(DateTime, default=_now)
    finished_at      = Column(DateTime, nullable=True)
    created_by       = Column(String, nullable=True)


class SecurityResult(Base):
    __tablename__ = "security_results"

    id                 = Column(String, primary_key=True, default=_uid)
    run_id             = Column(String, ForeignKey("security_runs.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    case_id            = Column(String, nullable=True)
    category           = Column(String, nullable=False)
    severity           = Column(String, default="high")
    attack_prompt      = Column(Text, nullable=True)     # denormalized for display
    expected_behavior  = Column(Text, nullable=True)
    agent_response     = Column(Text, nullable=True)
    retrieved_chunk_ids = Column(Text, nullable=True)    # JSON list
    verdict            = Column(String, nullable=True)   # VERDICTS
    detected_by        = Column(String, nullable=True)   # rule | judge
    evidence           = Column(Text, nullable=True)     # the proving fragment
    reasoning          = Column(Text, nullable=True)
    latency_ms         = Column(Float, nullable=True)
    tokens_used        = Column(Integer, nullable=True)
    created_at         = Column(DateTime, default=_now)

    __table_args__ = (Index("ix_security_results_run_verdict", "run_id", "verdict"),)
