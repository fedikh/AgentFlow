import uuid
from sqlalchemy import Column, Computed, String, Integer, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
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
    )

    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    content      = Column(Text, nullable=False)
    # PostgreSQL Full Text Search: GENERATED column — Postgres computes and
    # maintains it itself on every insert/update of `content` (no app code).
    # 'simple' config = language-neutral keyword tokens (no stemming), right
    # for a mixed FR/EN corpus with names/codes.
    content_tsv  = Column(TSVECTOR,
                          Computed("to_tsvector('simple', coalesce(content, ''))",
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
    chunk_meta   = Column(Text, nullable=True)     # JSON: {title, summary, keywords, entities, quality}
    content_hash = Column(String, nullable=True)   # md5 of content — duplicate detection
    token_count  = Column(Integer, nullable=True)  # real token count (context budgeting)
    lang         = Column(String, nullable=True)   # detected language (fr/en/…)
    document_id  = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    rag_space_id = Column(String, ForeignKey("rag_spaces.id", ondelete="CASCADE"), nullable=False)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relations
    document = relationship("Document", back_populates="chunks")
