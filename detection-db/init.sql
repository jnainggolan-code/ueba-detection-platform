-- =============================================================================
-- detection-db Initial Schema — UEBA Detection Platform
-- Engine: TimescaleDB 2.x (PostgreSQL 16)
-- Database: fraud_detection
-- =============================================================================

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =============================================================================
-- 1. entities
-- =============================================================================
CREATE TABLE entities (
    id SERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_value TEXT NOT NULL,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    profile_metadata JSONB,
    risk_score DOUBLE PRECISION DEFAULT 0.0,
    risk_level TEXT DEFAULT 'low',
    risk_factors JSONB,
    tags TEXT[],
    UNIQUE(entity_type, entity_value)
);
CREATE INDEX idx_entities_type ON entities (entity_type);
CREATE INDEX idx_entities_risk ON entities (risk_level, risk_score DESC);
CREATE INDEX idx_entities_last_seen ON entities (last_seen DESC);

-- =============================================================================
-- 2. logs_raw — Hypertable (1-day chunks)
-- =============================================================================
CREATE TABLE logs_raw (
    id BIGSERIAL,
    time TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (time, id),
    source TEXT NOT NULL,
    source_ip INET,
    log_level TEXT,
    raw_payload JSONB NOT NULL,
    parsed_data JSONB,
    parser_version TEXT,
    entity_id INTEGER REFERENCES entities(id),
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE
);
SELECT create_hypertable('logs_raw', 'time', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX idx_logs_raw_source ON logs_raw (source, time DESC);
CREATE INDEX idx_logs_raw_level ON logs_raw (log_level, time DESC);
CREATE INDEX idx_logs_raw_processed ON logs_raw (processed, time DESC) WHERE processed = FALSE;

-- =============================================================================
-- 3. behavior_baselines — Hypertable (7-day chunks)
-- =============================================================================
CREATE TABLE behavior_baselines (
    id BIGSERIAL,
    entity_id INTEGER REFERENCES entities(id),
    time TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (time, id),
    metric_name TEXT NOT NULL,
    metric_value DOUBLE PRECISION,
    baseline_mean DOUBLE PRECISION,
    baseline_stddev DOUBLE PRECISION,
    z_score DOUBLE PRECISION,
    is_anomaly BOOLEAN DEFAULT FALSE,
    anomaly_threshold DOUBLE PRECISION DEFAULT 3.0,
    window_start TIMESTAMPTZ,
    window_end TIMESTAMPTZ
);
SELECT create_hypertable('behavior_baselines', 'time', chunk_time_interval => INTERVAL '7 days');
CREATE INDEX idx_behavior_entity ON behavior_baselines (entity_id, time DESC);
CREATE INDEX idx_behavior_anomaly ON behavior_baselines (is_anomaly, time DESC);

-- =============================================================================
-- 4. anomaly_detections — Hypertable (1-day chunks)
-- =============================================================================
CREATE TABLE anomaly_detections (
    id BIGSERIAL,
    time TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (time, id),
    entity_id INTEGER REFERENCES entities(id),
    anomaly_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium',
    score DOUBLE PRECISION NOT NULL,
    z_score DOUBLE PRECISION,
    description TEXT,
    evidence JSONB,
    mitre_technique TEXT,
    mitre_tactic TEXT,
    status TEXT DEFAULT 'open',
    assigned_to TEXT,
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT
);
SELECT create_hypertable('anomaly_detections', 'time', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX idx_anomaly_entity ON anomaly_detections (entity_id, time DESC);
CREATE INDEX idx_anomaly_severity ON anomaly_detections (severity, time DESC);
CREATE INDEX idx_anomaly_status ON anomaly_detections (status);
CREATE INDEX idx_anomaly_open ON anomaly_detections (time DESC) WHERE status = 'open';

-- =============================================================================
-- 5. risk_scores — Hypertable (7-day chunks)
-- =============================================================================
CREATE TABLE risk_scores (
    id BIGSERIAL,
    entity_id INTEGER REFERENCES entities(id),
    time TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (time, id),
    overall_score DOUBLE PRECISION NOT NULL,
    component_scores JSONB,
    scoring_version TEXT,
    triggered_by BIGINT,
    decay_factor DOUBLE PRECISION DEFAULT 0.95
);
SELECT create_hypertable('risk_scores', 'time', chunk_time_interval => INTERVAL '7 days');
CREATE INDEX idx_risk_entity ON risk_scores (entity_id, time DESC);
CREATE INDEX idx_risk_score ON risk_scores (overall_score DESC, time DESC);

-- =============================================================================
-- 6. scoring_config
-- =============================================================================
CREATE TABLE scoring_config (
    id SERIAL PRIMARY KEY,
    anomaly_type TEXT NOT NULL UNIQUE,
    base_weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    z_score_threshold DOUBLE PRECISION NOT NULL DEFAULT 3.0,
    severity_mapping JSONB,
    decay_enabled BOOLEAN DEFAULT TRUE,
    decay_factor DOUBLE PRECISION DEFAULT 0.95,
    cooldown_minutes INTEGER DEFAULT 60,
    enabled BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default scoring configs
INSERT INTO scoring_config (anomaly_type, base_weight, z_score_threshold, severity_mapping, decay_factor)
VALUES
    ('login_frequency', 2.0, 3.0, '{"low": 1, "medium": 2, "high": 3, "critical": 4}', 0.95),
    ('geo_anomaly', 3.0, 3.5, '{"low": 1, "medium": 3, "high": 5, "critical": 7}', 0.90),
    ('time_anomaly', 1.5, 3.0, '{"low": 1, "medium": 2, "high": 3, "critical": 4}', 0.95),
    ('data_exfiltration', 4.0, 2.5, '{"low": 2, "medium": 4, "high": 6, "critical": 8}', 0.85),
    ('brute_force', 3.0, 3.0, '{"low": 1, "medium": 3, "high": 5, "critical": 6}', 0.90),
    ('privilege_escalation', 4.0, 2.0, '{"low": 2, "medium": 4, "high": 7, "critical": 10}', 0.80);

-- =============================================================================
-- Continuous Aggregates
-- =============================================================================

-- Risk daily summary
CREATE MATERIALIZED VIEW risk_daily_summary
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS day,
    entity_id,
    AVG(overall_score) AS avg_score,
    MAX(overall_score) AS max_score,
    MIN(overall_score) AS min_score,
    COUNT(*) AS readings
FROM risk_scores GROUP BY day, entity_id;

SELECT add_continuous_aggregate_policy('risk_daily_summary',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

-- Anomaly hourly counts
CREATE MATERIALIZED VIEW anomaly_hourly_counts
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS hour,
    anomaly_type, severity, COUNT(*) AS count
FROM anomaly_detections
GROUP BY hour, anomaly_type, severity;

SELECT add_continuous_aggregate_policy('anomaly_hourly_counts',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '30 minutes');

-- Entity activity summary
CREATE MATERIALIZED VIEW entity_activity_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS hour,
    entity_id, COUNT(*) AS total_events,
    COUNT(DISTINCT source) AS source_count,
    COUNT(*) FILTER (WHERE log_level = 'error') AS error_count,
    COUNT(*) FILTER (WHERE log_level = 'critical') AS critical_count
FROM logs_raw GROUP BY hour, entity_id;

SELECT add_continuous_aggregate_policy('entity_activity_hourly',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '15 minutes');

-- =============================================================================
-- Compression Policies
-- =============================================================================

ALTER TABLE logs_raw SET (timescaledb.compress,
    timescaledb.compress_segmentby = 'source',
    timescaledb.compress_orderby = 'time DESC');
SELECT add_compression_policy('logs_raw', INTERVAL '7 days');

ALTER TABLE behavior_baselines SET (timescaledb.compress,
    timescaledb.compress_segmentby = 'metric_name',
    timescaledb.compress_orderby = 'time DESC');
SELECT add_compression_policy('behavior_baselines', INTERVAL '30 days');

ALTER TABLE anomaly_detections SET (timescaledb.compress,
    timescaledb.compress_segmentby = 'severity',
    timescaledb.compress_orderby = 'time DESC');
SELECT add_compression_policy('anomaly_detections', INTERVAL '90 days');

ALTER TABLE risk_scores SET (timescaledb.compress,
    timescaledb.compress_segmentby = 'entity_id',
    timescaledb.compress_orderby = 'time DESC');
SELECT add_compression_policy('risk_scores', INTERVAL '30 days');

-- =============================================================================
-- Retention Policies
-- =============================================================================

SELECT add_retention_policy('logs_raw', INTERVAL '365 days');
SELECT add_retention_policy('behavior_baselines', INTERVAL '180 days');
SELECT add_retention_policy('risk_scores', INTERVAL '730 days');
