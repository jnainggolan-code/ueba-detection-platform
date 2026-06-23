# 🗄️ Database Schema — UEBA Detection Platform

> **Engine:** TimescaleDB 16 (PostgreSQL 16 + TimescaleDB extension)
> **Container:** `detection-db`
> **Port:** `5433`
> **Database:** `fraud_detection`
> **User:** `fraud`

---

## 📐 Architecture Overview

```
logs_raw (hypertable, 1-day chunks)
    │
    ├──► entities (regular table)
    │
    ├──► behavior_baselines (hypertable, 7-day chunks)
    │         └── continuous aggregate: hourly entity stats
    │
    ├──► anomaly_detections (hypertable, 1-day chunks)
    │         └── continuous aggregate: hourly anomaly counts
    │
    └──► risk_scores (hypertable, 7-day chunks)
              └── continuous aggregate: daily risk summary
```

---

## Tables

### logs_raw

```sql
CREATE TABLE logs_raw (
    id BIGSERIAL,
    time TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,
    source_ip INET,
    log_level TEXT,
    raw_payload JSONB NOT NULL,
    parsed_data JSONB,
    parser_version TEXT,
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE
);
SELECT create_hypertable('logs_raw', 'time', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX idx_logs_raw_source ON logs_raw (source, time DESC);
CREATE INDEX idx_logs_raw_level ON logs_raw (log_level, time DESC);
CREATE INDEX idx_logs_raw_processed ON logs_raw (processed, time DESC) WHERE processed = FALSE;
```

### entities

```sql
CREATE TABLE entities (
    id SERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_value TEXT NOT NULL,
    first_seen TIMESTAMPTZ NOT NULL,
    last_seen TIMESTAMPTZ NOT NULL,
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
```

### behavior_baselines

```sql
CREATE TABLE behavior_baselines (
    id BIGSERIAL,
    entity_id INTEGER REFERENCES entities(id),
    time TIMESTAMPTZ NOT NULL,
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
```

### anomaly_detections

```sql
CREATE TABLE anomaly_detections (
    id BIGSERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL,
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
```

### risk_scores

```sql
CREATE TABLE risk_scores (
    id BIGSERIAL,
    entity_id INTEGER REFERENCES entities(id),
    time TIMESTAMPTZ NOT NULL,
    overall_score DOUBLE PRECISION NOT NULL,
    component_scores JSONB,
    scoring_version TEXT,
    triggered_by BIGINT REFERENCES anomaly_detections(id),
    decay_factor DOUBLE PRECISION DEFAULT 0.95
);
SELECT create_hypertable('risk_scores', 'time', chunk_time_interval => INTERVAL '7 days');
CREATE INDEX idx_risk_entity ON risk_scores (entity_id, time DESC);
CREATE INDEX idx_risk_score ON risk_scores (overall_score DESC, time DESC);
```

### scoring_config

```sql
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
```

---


---

## Wazuh Alert Compatibility

Semua log yang masuk melalui endpoint `/api/v1/wazuh` disimpan di tabel `logs_raw` dengan `source = 'wazuh'`. Field spesifik Wazuh (seperti rule_id, agent info, MITRE ATT&CK) disimpan di kolom **`evidence`** (JSONB) pada tabel `anomaly_detections` saat parser mendeteksi anomaly.

### Evidence JSONB Structure

```json
{
  "wazuh_rule_id": 5710,
  "wazuh_rule_description": "sshd: Failed password on user root",
  "wazuh_rule_level": 10,
  "wazuh_agent_id": "001",
  "wazuh_agent_name": "soar-wazuh",
  "wazuh_agent_ip": "100.107.158.164",
  "wazuh_severity": "high",
  "wazuh_source_ip": "45.33.32.156",
  "wazuh_destination_user": "root",
  "wazuh_protocol": "ssh",
  "wazuh_attempts": 12,
  "wazuh_raw_alert": {
    "timestamp": "2026-06-23T08:00:00Z",
    "rule": {
      "id": 5710,
      "level": 10,
      "description": "sshd: Failed password"
    },
    "agent": {
      "id": "001",
      "name": "soar-wazuh"
    },
    "data": {
      "srcip": "45.33.32.156",
      "dstuser": "root"
    }
  },
  "mitre_technique_id": "T1110",
  "mitre_technique_name": "Brute Force",
  "mitre_tactic": "Credential Access"
}
```

### Query Examples

**Cari anomaly dari Wazuh berdasarkan rule_id:**
```sql
SELECT ad.time, e.entity_value, ad.anomaly_type, ad.severity, ad.score,
       ad.evidence->>'wazuh_rule_id' AS rule_id,
       ad.evidence->>'wazuh_rule_description' AS rule_desc
FROM anomaly_detections ad
JOIN entities e ON e.id = ad.entity_id
WHERE ad.evidence->>'wazuh_rule_id' = '5710'
  AND ad.time > NOW() - INTERVAL '7 days'
ORDER BY ad.time DESC;
```

**Cari semua alert dari Wazuh dengan severity tinggi:**
```sql
SELECT ad.time, e.entity_value, ad.anomaly_type, ad.score,
       ad.evidence->>'wazuh_source_ip' AS source_ip,
       ad.evidence->>'mitre_technique_name' AS mitre_technique
FROM anomaly_detections ad
JOIN entities e ON e.id = ad.entity_id
WHERE ad.severity IN ('high', 'critical')
  AND ad.evidence ? 'wazuh_rule_id'
ORDER BY ad.score DESC
LIMIT 50;
```

**Cari anomaly dari IP tertentu via Wazuh:**
```sql
SELECT ad.time, ad.anomaly_type, ad.severity,
       ad.evidence->>'wazuh_rule_description' AS description
FROM anomaly_detections ad
WHERE ad.evidence->>'wazuh_source_ip' = '45.33.32.156'
ORDER BY ad.time DESC;
```

### Wazuh Severity Mapping

Parser Wazuh otomatis memetakan `rule.level` (0-15) ke UEBA severity:

| Wazuh Level | UEBA Severity | Keterangan |
|:-----------:|:-------------:|:-----------|
| 0 - 3 | `low` | Informational events |
| 4 - 7 | `medium` | Unusual events / policy violations |
| 8 - 11 | `high` | Security threats / attacks |
| 12 - 15 | `critical` | Critical incidents / multi-attack |

### Keuntungan Opsi ini (JSONB)

- **Flexible**: Wazuh bisa nambah fields baru kapan aja tanpa alter table
- **No migration**: Tidak perlu perubahan skema database
- **Queryable**: JSONB di PostgreSQL mendukung indexing (`?`, `->>`, `@>` operators)
- **Self-documenting**: Setiap record lengkap dengan raw alert asli

## Continuous Aggregates

```sql
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
```

---

## Compression & Retention

```sql
-- Compression
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

-- Retention
SELECT add_retention_policy('logs_raw', INTERVAL '365 days');
SELECT add_retention_policy('behavior_baselines', INTERVAL '180 days');
SELECT add_retention_policy('risk_scores', INTERVAL '730 days');
```

---

## Query Examples

### Recent Open Alerts
```sql
SELECT ad.time, e.entity_type, e.entity_value, ad.anomaly_type,
       ad.severity, ad.score, ad.description, ad.status
FROM anomaly_detections ad
JOIN entities e ON e.id = ad.entity_id
WHERE ad.status = 'open'
ORDER BY ad.score DESC LIMIT 50;
```

### User Risk Timeline
```sql
SELECT time_bucket('1 hour', rs.time) AS hour,
       AVG(overall_score), MAX(overall_score)
FROM risk_scores rs
JOIN entities e ON e.id = rs.entity_id
WHERE e.entity_value = 'jnainggolan'
  AND rs.time > NOW() - INTERVAL '7 days'
GROUP BY hour ORDER BY hour;
```

### Top Risk Entities
```sql
SELECT e.entity_type, e.entity_value, e.risk_score, e.risk_level,
       COUNT(ad.id) AS total_alerts, MAX(ad.time) AS last_alert
FROM entities e
LEFT JOIN anomaly_detections ad ON ad.entity_id = e.id
    AND ad.time > NOW() - INTERVAL '7 days'
WHERE e.risk_level IN ('high', 'critical')
GROUP BY e.id ORDER BY e.risk_score DESC LIMIT 20;
```

### Anomaly Trend (24h)
```sql
SELECT time_bucket('1 hour', time) AS hour,
       anomaly_type, COUNT(*) AS count
FROM anomaly_detections
WHERE time > NOW() - INTERVAL '24 hours'
GROUP BY hour, anomaly_type ORDER BY hour;
```

---

## Network
---

## 🌐 Network (Netbird)

Semua server terhubung via **Netbird VPN** (100.107.x.x/16).

| Server | Netbird IP | Fungsi |
|:-------|:-----------|:-------|
| **soar-wazuh** | `100.107.158.164` | Wazuh Manager — kirim alert via webhook |
| **soar-node3** | `100.107.105.81` | Syslog forwarder — kirim log ke detection-api |
| **soar-dashboard** | `100.107.189.94` | UEBA Detection Platform (detection-api, detection-db, detection-dashboard) |

### Webhook Direct ke soar-dashboard
Source yang kirim data langsung (bukan lewat node3):
- **Wazuh** → `http://100.107.189.94:8081/api/v1/wazuh`
- **Delinea PAM** → `http://100.107.189.94:8081/api/v1/delinea`


## Related Documentation

| Doc | Path | Description |
|:----|:-----|:------------|
| Setup | `docs/SETUP.md` | Installation & configuration |
| API | `docs/API.md` | API endpoints & usage |
| Architecture | `docs/ARCHITECTURE.md` | System architecture & data flow |

> **Last updated:** 2026-06-23
