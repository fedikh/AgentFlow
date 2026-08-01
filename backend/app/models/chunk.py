import uuid
from sqlalchemy import Column, Computed, String, Integer, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Chunk(Base):
    """One chunk of a document — TEXT + metadata only. The chunk's vector
    lives in the per-dimension bucket table chunk_vectors_<dim> (see
    services/pgvector_store.py), linked by this row's id with ON DELETE
    CASCADE — so deleting a chunk deletes its vector automatically."""
    __tablename__ = "chunks"
    __table_args__ = (
        # GIN index — makes @@ full-text queries fast
        Index("chunks_content_tsv_gin", "content_tsv", postgresql_using="gin"),
        # Trigram GIN index — fuzzy matching (pg_trgm <% / word_similarity)
        # for typo-tolerant keyword search on codes and names
        Index("chunks_content_trgm_gin", "content",
              postgresql_using="gin", postgresql_ops={"content": "gin_trgm_ops"}),
        # JSONB GIN (jsonb_path_ops) — fast @> containment for the Metadata
        # Filter Builder (e.g. chunk_meta @> '{"keywords": ["congés"]}')
        Index("chunks_chunk_meta_gin", "chunk_meta",
              postgresql_using="gin", postgresql_ops={"chunk_meta": "jsonb_path_ops"}),
    )

    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    content      = Column(Text, nullable=False)
    # PostgreSQL Full Text Search: GENERATED column — Postgres computes and
    # maintains it itself on every insert/update (no app code). LANGUAGE-AWARE:
    # the row's detected `lang` picks the stemming config (french/english),
    # anything else falls back to 'simple' (plain keyword tokens). The keyword
    # retriever mirrors this at query time (detected query language + simple).
    content_tsv  = Column(TSVECTOR, Computed(
        "to_tsvector("
        "CASE WHEN lang = 'fr' THEN 'french'::regconfig "
        "     WHEN lang = 'en' THEN 'english'::regconfig "
        "     ELSE 'simple'::regconfig END, "
        "coalesce(content, ''))",
        persisted=True))
    page         = Column(Integer, default=0)
    chunk_index  = Column(Integer, default=0)
    # Batch 5: mark image chunks so the chat can render them inline.
    #   chunk_type: "text" | "table" | "image_summary"
    #   image_path: absolute path of the saved image (only for image_summary)
    chunk_type   = Column(String, default="text")
    image_path   = Column(String, nullable=True)
    # Which strategy produced this chunk, and (for hierarchical) the chunk_index
    # of its parent chunk within the same document.
    strategy     = Column(String, nullable=True)
    parent_index = Column(Integer, nullable=True)
    # ── Chunk metadata carried from parsing/chunking ──
    section_path = Column(String, nullable=True)   # heading breadcrumb ("3. Congés > 3.2 Annuels")
    chunk_meta   = Column(JSONB, nullable=True)    # {title, summary, keywords, entities, quality}
    content_hash = Column(String, nullable=True)   # md5 of content — duplicate detection
    token_count  = Column(Integer, nullable=True)  # real token count (context budgeting)
    lang         = Column(String, nullable=True)   # detected language (fr/en/…)
    document_id  = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    rag_space_id = Column(String, ForeignKey("rag_spaces.id", ondelete="CASCADE"), nullable=False)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relations
    document = relationship("Document", back_populates="chunks")
