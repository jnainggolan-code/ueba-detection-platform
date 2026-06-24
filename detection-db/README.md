# 🗄️ detection-db — UEBA Detection Platform

TimescaleDB container untuk menyimpan semua data UEBA Detection Platform.

## 📋 Overview

Container ini menjalankan **TimescaleDB 2.x on PostgreSQL 16** dan digunakan sebagai primary data store untuk:
- Log events (normalized & raw)
- Entity baselines & behavior profiles
- Anomaly detections
- Risk scores & scoring configurations

## 🔌 Connection

| Parameter | Value |
|:----------|:------|
| **Host** | `detection-db` (Docker internal) |
| **Port** | `5433` |
| **Database** | `fraud_detection` |
| **User** | `fraud` |

## 📦 Tables

| Table | Type | Description |
|:------|:-----|:------------|
| `logs_raw` | Hypertable (1d) | Raw log events from all sources |
| `entities` | Regular | Entity/user profiles & metadata |
| `behavior_baselines` | Hypertable (7d) | Behavioral baseline metrics |
| `anomaly_detections` | Hypertable (1d) | Detected anomalies & alerts |
| `risk_scores` | Hypertable (7d) | Risk score calculations |
| `scoring_config` | Regular | Scoring configuration |

## 🏗️ Schema

Full schema: see `init.sql` and `functions.sql`

### Hypertable Chunking

| Hypertable | Chunk Interval | Compression After | Retention |
|:-----------|:---------------|:------------------|:----------|
| `logs_raw` | 1 day | 7 days | 365 days |
| `behavior_baselines` | 7 days | 30 days | 180 days |
| `anomaly_detections` | 1 day | 90 days | — |
| `risk_scores` | 7 days | 30 days | 730 days |

## 🧮 Database Functions

| Function | Description |
|:---------|:------------|
| `fn_calculate_risk_decay()` | Exponential decay factor: `0.95 ^ hours_since` |
| `fn_get_entity_risk(entity_id)` | Current risk score + level for an entity |
| `fn_update_entity_risk()` | Trigger: auto-update entity risk on anomaly insert |
| `fn_generate_alert()` | Generate alert from anomaly detection |

## 🚀 Usage

### Build
```bash
docker build -t detection-db .
```

### Run
```bash
docker run -d \
  --name detection-db \
  -p 5433:5432 \
  -e POSTGRES_DB=fraud_detection \
  -e POSTGRES_USER=fraud \
  -e POSTGRES_PASSWORD=yourpassword \
  detection-db
```

### Docker Compose
```yaml
services:
  detection-db:
    build: ./detection-db
    ports:
      - "5433:5432"
    environment:
      POSTGRES_DB: fraud_detection
      POSTGRES_USER: fraud
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - detection-db-data:/var/lib/postgresql/data

volumes:
  detection-db-data:
```

## 🔐 Security

- Port 5433 hanya bisa diakses dari detection-api via Docker network
- Jangan expose ke publik
- Ganti password default di `.env`
- Gunakan volume terpisah untuk data persistence

## 📁 File Structure

```
detection-db/
├── Dockerfile          # Container image definition
├── init.sql            # Initial schema + indexes + policies
├── functions.sql       # Stored procedures & functions
├── .env.example        # Environment variable template
└── README.md           # This file
```
