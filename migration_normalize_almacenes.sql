-- Migration: Normalize almacenes to reference catalog_centros
-- Run this SQL script against spm.db to normalize the schema.

-- Step 1: Create catalog_centros if not exists
CREATE TABLE IF NOT EXISTS catalog_centros (
  id INTEGER PRIMARY KEY,
  codigo TEXT NOT NULL UNIQUE,
  nombre TEXT NOT NULL,
  activo INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Step 2: Add centro_codigo column to almacenes
PRAGMA foreign_keys=off;
BEGIN TRANSACTION;

-- Add new column
ALTER TABLE almacenes ADD COLUMN centro_codigo TEXT;

-- Backfill from existing centro column (assuming it stores codes)
UPDATE almacenes SET centro_codigo = centro WHERE centro_codigo IS NULL;

-- Seed catalog_centros with distinct codes from almacenes
INSERT OR IGNORE INTO catalog_centros(codigo, nombre, activo)
SELECT DISTINCT centro_codigo, centro_codigo, 1 FROM almacenes WHERE centro_codigo IS NOT NULL;

-- Create new almacenes table with proper FK
CREATE TABLE almacenes_new (
  id INTEGER PRIMARY KEY,
  codigo TEXT NOT NULL,
  nombre TEXT NOT NULL,
  centro_codigo TEXT NOT NULL,
  activo INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (codigo, centro_codigo),
  FOREIGN KEY (centro_codigo) REFERENCES catalog_centros(codigo) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- Migrate data
INSERT INTO almacenes_new(id, codigo, nombre, centro_codigo, activo, created_at, updated_at)
SELECT id, codigo, nombre, centro_codigo, COALESCE(activo, 1), COALESCE(created_at, CURRENT_TIMESTAMP), COALESCE(updated_at, CURRENT_TIMESTAMP)
FROM almacenes;

-- Drop old table and rename
DROP TABLE almacenes;
ALTER TABLE almacenes_new RENAME TO almacenes;

-- Create index
CREATE INDEX IF NOT EXISTS idx_almacenes_centro ON almacenes(centro_codigo);

COMMIT;
PRAGMA foreign_keys=on;