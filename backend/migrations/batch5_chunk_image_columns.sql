-- ════════════════════════════════════════════════════════════════
-- Batch 5 — Chat returns images
-- Add chunk_type + image_path columns to the chunks table.
--
-- REQUIRED: Base.metadata.create_all does NOT alter existing tables, so this
-- migration MUST be run before re-processing documents. New image chunks are
-- inserted with these columns; without them the INSERT will fail.
--
-- After running this, RE-PROCESS (re-index) documents that contain images so
-- image_summary chunks are created (previously image blocks were dropped).
-- ════════════════════════════════════════════════════════════════

ALTER TABLE chunks ADD COLUMN IF NOT EXISTS chunk_type VARCHAR DEFAULT 'text';
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS image_path VARCHAR;

-- Backfill existing rows to the default type
UPDATE chunks SET chunk_type = 'text' WHERE chunk_type IS NULL;
