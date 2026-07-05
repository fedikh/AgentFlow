-- ════════════════════════════════════════════════════════════════
-- Batch 1 — RAG space per-user access control
-- Table: rag_space_access  (many-to-many: space <-> allowed user)
--
-- NOTE: the app also auto-creates this table via Base.metadata.create_all
-- on startup. Run this SQL only if you prefer an explicit migration.
-- ════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS rag_space_access (
    id            VARCHAR PRIMARY KEY,
    rag_space_id  VARCHAR NOT NULL REFERENCES rag_spaces(id) ON DELETE CASCADE,
    user_id       VARCHAR NOT NULL REFERENCES users(id)      ON DELETE CASCADE,
    CONSTRAINT uq_space_user UNIQUE (rag_space_id, user_id)
);

CREATE INDEX IF NOT EXISTS ix_rag_space_access_space ON rag_space_access (rag_space_id);
CREATE INDEX IF NOT EXISTS ix_rag_space_access_user  ON rag_space_access (user_id);
