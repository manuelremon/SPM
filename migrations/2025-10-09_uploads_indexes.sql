CREATE INDEX IF NOT EXISTS idx_uploads_owner_created ON uploads(owner, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_uploads_owner_name ON uploads(owner, original_name);
