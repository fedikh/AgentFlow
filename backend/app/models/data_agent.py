"""
Data Agent (NL → SQL) — models. Created by create_all like every other table.

    data_sources          one connected enterprise database (PG / MySQL / MSSQL).
                          Credentials Fernet-encrypted; carries the SAME
                          LLM/embedding source fields as rag_spaces so the
                          existing factories resolve models with zero new
                          plumbing.
    data_source_tables    introspected tables  (+ LLM-bootstrapped, editable
    data_source_columns    and columns          descriptions)
    data_source_glossary  business terms ("chiffre d'affaires" = …)
    data_source_examples  question → SQL pairs; ONLY verified ones are trained
    data_source_access    mirror of rag_space_access: empty = whole department
    data_agent_sessions   per-user conversations (mirror of models/chat.py)
    data_agent_messages   every turn; assistant rows keep the generated SQL,
                          attempts, validation errors, timings, decision trace

AgentFlow tables are the source of truth — Vanna's store is a derived index.
Conventions: String UUID PKs, status as plain String (new statuses must never
need a migration), params as Text JSON, naive-UTC timestamps.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (Boolean, Column, DateTime, Float, ForeignKey, Index,
                        Integer, String, Text)
from sqlalchemy.orm import relationship

from app.database import Base


def _now():
    return datetime.now(timezone.utc)


def _uid():
    return str(uuid.uuid4())


class DataSource(Base):
    __tablename__ = "data_sources"

    id          = Column(String, primary_key=True, default=_uid)
    name        = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    dialect     = Column(String, nullable=False)       # postgres | mysql | mssql
    host     = Column(String, nullable=False)
    port     = Column(Integer, nullable=False)
    database = Column(String, nullable=False)
    username = Column(String, nullable=False)
    password_enc = Column(Text, nullable=True)         # Fernet (providers_crypto)
    extra_params = Column(Text, nullable=True)         # JSON: odbc driver, sslmode…
    schema_whitelist = Column(Text, nullable=True)     # JSON list[str]; empty = all

    table_count   = Column(Integer, default=0)
    mode_auto     = Column(String, default="base")     # base | rag
    mode_override = Column(String, nullable=True)
    row_limit     = Column(Integer, default=1000)
    timeout_ms    = Column(Integer, default=30000)
    status        = Column(String, default="draft")    # draft|connected|trained|stale|error
    last_error    = Column(Text, nullable=True)
    send_results_to_llm = Column(Boolean, default=False)

    # ── generation config (Models panel) ──
    llm_temperature = Column(Float, default=0.0)       # SQL wants determinism
    llm_max_tokens  = Column(Integer, default=2000)
    prompt_mode     = Column(String, default="default")  # default | custom
    system_prompt   = Column(Text, nullable=True)      # used when prompt_mode=custom

    # ── JSON configs (the retrieval_params convention) ──
    retrieval_params = Column(Text, nullable=True)     # hybrid/rrf/top-k per index
    chunk_params     = Column(Text, nullable=True)     # per-format chunking strategy

    # model sources — SAME shape as rag_spaces so llm_factory/embedding_factory
    # resolve them unchanged (company provider → own key → env)
    llm_provider    = Column(String, default="GROQ")
    llm_model       = Column(String, default="llama-3.3-70b-versatile")
    llm_provider_id = Column(String, nullable=True)
    llm_api_key_enc = Column(Text, nullable=True)
    llm_base_url    = Column(String, nullable=True)
    embedding_provider    = Column(String, default="LOCAL")
    embedding_model       = Column(String, default="BAAI/bge-m3")
    embedding_provider_id = Column(String, nullable=True)
    embedding_api_key_enc = Column(Text, nullable=True)
    embedding_base_url    = Column(String, nullable=True)
    embedding_dim         = Column(Integer, nullable=True)

    # Visibility (RAG rule): private = only the owner/IT see it, even when
    # deployed. Deploy flips it to department-visible.
    is_private = Column(Boolean, default=True)

    # Knowledge documents live in a HIDDEN RAG space, so ingestion (loaders →
    # parsers → chunking → pgvector) and retrieval are the platform's ONE
    # implementation — not a second one.
    knowledge_space_id = Column(String, nullable=True)

    owner_id        = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    department_id   = Column(String, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    organization_id = Column(String, nullable=False, index=True)

    last_introspected_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    tables = relationship("DataSourceTable", cascade="all, delete-orphan",
                          back_populates="source")
    versions = relationship("DataSourceVersion", cascade="all, delete-orphan")


class DataSourceVersion(Base):
    """Config snapshot of a data agent (mirror of rag_space_versions).

    A version stores the PIPELINE config only — generation, models, retrieval,
    execution safety — never the connection identity (host, credentials) and
    never the trained index. The deployed version is the row whose status is
    DEPLOYED (exactly one per source; deploying archives the previous one), so
    no pointer column is needed on data_sources."""
    __tablename__ = "data_source_versions"

    id             = Column(String, primary_key=True, default=_uid)
    data_source_id = Column(String, ForeignKey("data_sources.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    version_number = Column(Integer, nullable=False, default=1)
    label          = Column(String, nullable=False, default="v1")
    status         = Column(String, nullable=False, default="SAVED")  # SAVED|DEPLOYED|ARCHIVED
    notes          = Column(Text, nullable=True)
    config         = Column(Text, nullable=True)       # JSON snapshot
    created_by     = Column(String, ForeignKey("users.id", ondelete="SET NULL"),
                            nullable=True)
    created_at     = Column(DateTime, default=_now)

    __table_args__ = (
        Index("ix_data_source_versions_source_number",
              "data_source_id", "version_number", unique=True),
    )


class DataSourceTable(Base):
    __tablename__ = "data_source_tables"

    id             = Column(String, primary_key=True, default=_uid)
    data_source_id = Column(String, ForeignKey("data_sources.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    schema_name = Column(String, nullable=False)
    table_name  = Column(String, nullable=False)
    table_type  = Column(String, default="table")      # table | view
    description = Column(Text, nullable=True)          # LLM-bootstrapped, editable
    row_count_estimate = Column(Integer, nullable=True)
    is_enabled  = Column(Boolean, default=True)        # disabled → never trained

    source  = relationship("DataSource", back_populates="tables")
    columns = relationship("DataSourceColumn", cascade="all, delete-orphan",
                           back_populates="table")


class DataSourceColumn(Base):
    __tablename__ = "data_source_columns"

    id       = Column(String, primary_key=True, default=_uid)
    table_id = Column(String, ForeignKey("data_source_tables.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    column_name    = Column(String, nullable=False)
    data_type      = Column(String, nullable=False)
    is_nullable    = Column(Boolean, default=True)
    is_primary_key = Column(Boolean, default=False)
    foreign_key_ref = Column(String, nullable=True)    # "schema.table.column"
    description    = Column(Text, nullable=True)
    sample_values  = Column(Text, nullable=True)       # JSON list (low-cardinality only)

    table = relationship("DataSourceTable", back_populates="columns")


class DataSourceGlossary(Base):
    __tablename__ = "data_source_glossary"

    id             = Column(String, primary_key=True, default=_uid)
    data_source_id = Column(String, ForeignKey("data_sources.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    term       = Column(String, nullable=False)
    definition = Column(Text, nullable=False)


class DataSourceExample(Base):
    __tablename__ = "data_source_examples"

    id             = Column(String, primary_key=True, default=_uid)
    data_source_id = Column(String, ForeignKey("data_sources.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    question    = Column(Text, nullable=False)
    sql         = Column(Text, nullable=False)
    is_verified = Column(Boolean, default=False)       # only verified pairs trained
    created_by  = Column(String, nullable=True)
    created_at  = Column(DateTime, default=_now)


class DataSourceAccess(Base):
    """Mirror of rag_space_access: no rows = every department end user may ask."""
    __tablename__ = "data_source_access"

    id             = Column(String, primary_key=True, default=_uid)
    data_source_id = Column(String, ForeignKey("data_sources.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    user_id        = Column(String, ForeignKey("users.id", ondelete="CASCADE"),
                            nullable=False, index=True)


class DataAgentSession(Base):
    __tablename__ = "data_agent_sessions"

    id             = Column(String, primary_key=True, default=_uid)
    user_id        = Column(String, ForeignKey("users.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    data_source_id = Column(String, ForeignKey("data_sources.id", ondelete="CASCADE"),
                            nullable=True, index=True)   # null until first routed question
    title  = Column(String, default="New chat")
    status = Column(String, default="ACTIVE")            # ACTIVE | ARCHIVED
    message_count   = Column(Integer, default=0)
    last_message_at = Column(DateTime, default=_now)
    created_at      = Column(DateTime, default=_now)

    messages = relationship("DataAgentMessage", cascade="all, delete-orphan",
                            back_populates="session",
                            order_by="DataAgentMessage.created_at")

    __table_args__ = (
        Index("ix_data_agent_sessions_user_last", "user_id", "last_message_at"),
    )


class DataAgentMessage(Base):
    __tablename__ = "data_agent_messages"

    id         = Column(String, primary_key=True, default=_uid)
    session_id = Column(String, ForeignKey("data_agent_sessions.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    role    = Column(String, nullable=False)             # user | assistant
    content = Column(Text, nullable=False)               # question / NL answer

    # assistant rows — the full trace of how the answer was produced
    generated_sql     = Column(Text, nullable=True)
    dialect           = Column(String, nullable=True)
    attempts          = Column(Integer, nullable=True)
    validation_errors = Column(Text, nullable=True)      # JSON list
    row_count         = Column(Integer, nullable=True)
    truncated         = Column(Boolean, nullable=True)
    timings_ms        = Column(Text, nullable=True)      # JSON dict
    decision_trace    = Column(Text, nullable=True)      # JSON dict
    created_at        = Column(DateTime, default=_now)

    session = relationship("DataAgentSession", back_populates="messages")
