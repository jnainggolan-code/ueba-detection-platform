-- =============================================================================
-- Migration 003: Search Performance Optimization
-- Adds indexes for common query patterns and pg_trgm for fuzzy search
-- =============================================================================

-- 1. Enable pg_trgm for fuzzy/partial text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 2. BTREE indexes on extracted JSONB fields for entity/event_type filters
-- These use the ->> operator pattern that our queries actually use
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_logs_raw_entity_id
  ON logs_raw ((parsed_data->>'entity_id'), time DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_logs_raw_event_type
  ON logs_raw ((parsed_data->>'event_type'), time DESC);

-- 3. GIN index with jsonb_path_ops for containment queries (@> operator)
-- Faster than default GIN ops when doing key/value lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_logs_raw_parsed_data_path
  ON logs_raw USING gin (parsed_data jsonb_path_ops);

-- 4. pg_trgm GIN index on raw_payload text for ILIKE/fuzzy search fallback
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_logs_raw_payload_trgm
  ON logs_raw USING gin (cast(raw_payload as text) gin_trgm_ops);

-- 5. Drop the old default-ops GIN index (slower than jsonb_path_ops for our use case)
-- Keep for now, can be dropped after verifying new indexes work
