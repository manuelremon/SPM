CREATE TABLE IF NOT EXISTS uploads(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner TEXT NOT NULL,
  original_name TEXT NOT NULL,
  stored_name TEXT NOT NULL,
  size INTEGER NOT NULL,
  mime TEXT,
  sha256 TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_uploads_owner ON uploads(owner);
CREATE UNIQUE INDEX IF NOT EXISTS idx_uploads_sha ON uploads(sha256, owner);
