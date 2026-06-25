# 🏗️ Architecture — UEBA Detection Platform

> **Deployment:** soar-dashboard (100.107.189.94)
> **Network:** Netbird (100.107.x.x/16)

---

## System Overview

```
╔══════════════════════════════════════════════════════════════════════╗
║                          🎯  S O U R C E S                          ║
║                                                                      ║
║   ╔══════════╗  ╔══════════╗  ╔══════════╗  ╔══════════════╗        ║
║   ║  SYSNLOG ║  ║  WAZUH   ║  ║   RAW    ║  ║  DELINEA PAM ║        ║
║   ║  (UDP)   ║  ║ (Webhook)║  ║  (HTTP)  ║  ║  (Webhook)   ║        ║
║   ╚════╤═════╝  ╚════╤═════╝  ╚════╤═════╝  ╚══════╤═══════╝        ║
║        │              │              │              │               ║
║        └──────────────┼──────────────┼──────────────┘               ║
║                       │              │                              ║
║              ╔════════▼══════════════▼══════════╗                   ║
║              ║        SOAR-NODE3                 ║                   ║
║              ║      100.107.105.81               ║                   ║
║              ║    (rsyslog forwarder)            ║                   ║
║              ╚═══════════╤═══════════════════════╝                   ║
║                          │  Netbird VPN (100.107.x.x/16)           ║
╚══════════════════════════╪═══════════════════════════════════════════╝
                           │
╔══════════════════════════▼═══════════════════════════════════════════╗
║                   🏢  SOAR-DASHBOARD                                 ║
║                     100.107.189.94                                   ║
║                                                                      ║
║   ╔═════════════════════════════════════════════════════════════╗    ║
║   ║              🐍  DETECTION-API  (FastAPI)                   ║    ║
║   ║                    Port 8081                                ║    ║
║   ║                                                             ║    ║
║   ║  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      ║    ║
║   ║  │ /ingest  │ │ /process │ │ /wazuh   │ │ /delinea │      ║    ║
║   ║  │(syslog)  │ │  (raw)   │ │(webhook) │ │(webhook) │      ║    ║
║   ║  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘      ║    ║
║   ║       │             │             │             │          ║    ║
║   ║       └─────────────┼─────────────┼─────────────┘          ║    ║
║   ║                     ▼             ▼                        ║    ║
║   ║           ┌──────────────────────────────┐                 ║    ║
║   ║           │     P A R S E R S             │                ║    ║
║   ║           │  Syslog │ Raw │ Wazuh │ Delinea│              ║    ║
║   ║           └──────────────┬───────────────┘                 ║    ║
║   ║                          ▼                                ║    ║
║   ║           ┌──────────────────────────────┐                 ║    ║
║   ║           │   S E R V I C E S            │                ║    ║
║   ║           │  Ingestion → Scoring → Anomaly│               ║    ║
║   ║           │  ├ risk_scoring_engine       │                ║    ║
║   ║           │  ├ anomaly_detector          │                ║    ║
║   ║           │  ├ rule_engine               │                ║    ║
║   ║           │  └ peer_group_analyzer       │                ║    ║
║   ║           └──────────────┬───────────────┘                 ║    ║
║   ║                          ▼                                ║    ║
║   ║           ┌──────────────────────────────┐                 ║    ║
║   ║           │   R E P O S I T O R I E S    │                ║    ║
║   ║           │  logs │ behaviors │ risk    │                 ║    ║
║   ║           │  (Async SQLAlchemy 2.0)     │                 ║    ║
║   ║           └──────────────┬───────────────┘                 ║    ║
║   ╚═════════════════════════╪══════════════════════════════════╝    ║
║                              │                                      ║
║   ╔══════════════════════════▼══════════════════════════════════╗    ║
║   ║          🗄️  DETECTION-DB  (TimescaleDB)                  ║    ║
║   ║                   Port 5433                                ║    ║
║   ║                                                             ║    ║
║   ║  ┌────────────┐ ┌──────────────┐ ┌──────────────────┐      ║    ║
║   ║  │  logs_raw  │ │  behavior_   │ │  anomaly_        │      ║    ║
║   ║  │(hypertable)│ │  baselines   │ │  detections      │      ║    ║
║   ║  │  1d chunks │ │(hypertable)  │ │  (hypertable)    │      ║    ║
║   ║  │            │ │  7d chunks   │ │  1d chunks       │      ║    ║
║   ║  └────────────┘ └──────────────┘ └──────────────────┘      ║    ║
║   ║  ┌────────────┐ ┌──────────────┐ ┌──────────────────┐      ║    ║
║   ║  │ risk_scores│ │   entities   │ │  scoring_config  │      ║    ║
║   ║  │(hypertable)│ │  (regular)   │ │  (regular)       │      ║    ║
║   ║  └────────────┘ └──────────────┘ └──────────────────┘      ║    ║
║   ║  ┌────────────┐                                            ║    ║
║   ║  │custom_rules│                                            ║    ║
║   ║  │ (regular)  │                                            ║    ║      ║    ║
║   ║  │  7d chunks │ │              │ │                  │      ║    ║
║   ║  └────────────┘ └──────────────┘ └──────────────────┘      ║    ║
║   ╚══════════════════════════╤══════════════════════════════════╝    ║
║                              │                                      ║
║   ╔══════════════════════════▼══════════════════════════════════╗    ║
║   ║    🎨  DETECTION-DASHBOARD  (React + TypeScript)          ║    ║
║   ║                   Port 8082                                ║    ║
║   ║                                                             ║    ║
║   ║  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      ║    ║
║   ║  │  📋 Log      │  │  👤 User     │  │  🔥 Risk     │     ║    ║
║   ║  │  Viewer      │  │  Detection   │  │  Heatmap     │      ║    ║
║   ║  │  (TanStack)  │  │  (Recharts)  │  │  (Recharts)  │      ║    ║
║   ║  └──────────────┘  └──────────────┘  └──────────────┘      ║    ║
║   ║  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      ║    ║
║   ║  │  🔔 Alerts   │  │  📊 Reports  │  │  ⚙️ Settings │     ║    ║
║   ║  │  Timeline    │  │  Generator   │  │  Config      │      ║    ║
║   ║  └──────────────┘  └──────────────┘  └──────────────┘      ║    ║
║   ╚═════════════════════════════════════════════════════════════╝    ║
╚══════════════════════════════════════════════════════════════════════╝
```

### Arus Data

```
WEBHOOK DIRECT (tanpa node3):
   Wazuh (100.107.158.164)  ──►  POST /api/v1/wazuh   ──► detection-api:8081
   Delinea PAM              ──►  POST /api/v1/delinea ──► detection-api:8081

VIA SOAR-NODE3:
   Syslog    ──► soar-node3 (100.107.105.81) ──► POST /api/v1/ingest  ──► detection-api:8081
   Raw Logs  ──► soar-node3 (100.107.105.81) ──► POST /api/v1/process ──► detection-api:8081

PROSESING:
   detection-api:8081 ──► Parser ──► Service (scoring + anomaly) ──► Repository ──► detection-db:5433
                                                                                      │
                                                                                      ▼
                                                                          detection-dashboard:8082


---

## Container Design

| Container | Image | Port | Base | Scaling |
|:----------|:------|:-----|:-----|:--------|
| `detection-api` | Custom | 8081 | python:3.12-slim | Horizontal |
| `detection-worker` | Custom | — | python:3.12-slim | Horizontal |
| `detection-redis` | Redis 7 | 6379 | redis:7-alpine | Vertical |
| `detection-dashboard` | Nginx | 8082 | nginx:alpine | Horizontal |
| `detection-db` | TimescaleDB | 5433 | timescale/timescaledb:latest-pg16 | Vertical |

## Data Flow

### Pipeline (Worker Container)

```
Wazuh Event -> POST /api/v2/wazuh -> enqueue RQ job
                                          |
                                     RQ Worker
                                          |
                              +-----------+
                              |
                      1. Fetch event from DB by ID
                      2. Anomaly Detection (z-score)
                      3. Risk Scoring (decay + weight)
                      4. Rule Engine evaluation
                      5. Commit to DB
```

### Ingestion Pipeline


```
Source → soar-node3 → API Gateway → Parser → Repository → TimescaleDB
                                                              │
                                                        Scoring Engine
                                                              │
                                                     Anomaly Detection
                                                              │
                                          ┌────────────────────┼────────────┐
                                          ▼                    ▼            ▼
                                   anomaly_detections    entities     risk_scores
```

### Rule Engine

```
Event -> risk scoring -> evaluate_all_rules()
                            |
                    +-------|--------+
                    |                |
              conditions      frequency check
                    |                |
                    +--------+-------+
                             |
                     execute_action()
                             |
                    create_alert() -> anomaly_detections
```

### Scoring Algorithm


```
risk_score = Σ(anomaly_score × weight × decay_factor)

anomaly_score = min(100, (|z_score| / threshold) × 100)
weight = scoring_config.base_weight
decay_factor = 0.95^hours_since
```

---

## Technology Stack

| Layer | Technology | Purpose |
|:------|:-----------|:--------|
| API | FastAPI 0.110+ | Async Python framework |
| ORM | SQLAlchemy 2.0 | Async DB access |
| DB | TimescaleDB 16 | Time-series + PostgreSQL |
| Dashboard | React 18 + TypeScript | Frontend SPA |
| UI | shadcn/ui + Recharts | Components + charts |
| Styling | Tailwind CSS 3 | Utility-first CSS |
| State | Zustand 4 | Client state |
| Container | Docker 24 + Compose 2.20 | Runtime + orchestration |

---

## Network

```
soar-wazuh ──► soar-node3 ──► detection-api:8081 ──► detection-db:5433
                                  │
                            detection-dashboard:8082
                                  │
                             User Browser
```

### Ports

| Port | Service | Access |
|:-----|:--------|:-------|
| 8081 | detection-api | Netbird / localhost |
| 8082 | detection-dashboard | Netbird + proxy |
| 5433 | detection-db | Netbird only |

---

## Scaling

### Horizontal (detection-api)
```bash
docker compose up -d --scale detection-api=3
```
- Stateless (no local storage)
- DB pool: pool_size=20 per instance

### Vertical (detection-db)
- Tune chunk intervals by data volume
- Compression for cold data (>7 days)
- Continuous aggregates for dashboard

### Storage Estimate
| Item | Estimate |
|:-----|:---------|
| Logs/day | ~500 MB raw (~100 MB compressed) |
| Entities | ~1,000 active |
| Retention | 365 days |
| Total | ~36 GB compressed |

---

## Security

### Auth Layers
```
Client → Reverse Proxy (TLS) → API Gateway (API Key) → Service (JWT)
```

### Key Hierarchy
```
admin:*           → Full access
ingest:syslog    → POST /api/v1/ingest only
ingest:raw       → POST /api/v1/process only
ingest:wazuh     → POST /api/v1/wazuh only
dashboard:read   → GET endpoints only
```

### Network
- DB hanya dari detection-api
- API hanya via Netbird
- Dashboard bisa dengan reverse proxy

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


## Related Docs

| Doc | Path |
|:----|:-----|
| Setup | `docs/SETUP.md` |
| API | `docs/API.md` |
| Database | `docs/DATABASE.md` |

> **Last updated:** 2026-06-23
