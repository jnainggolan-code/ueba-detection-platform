# 🏗️ Architecture — UEBA Detection Platform

> **Deployment:** soar-dashboard (100.107.189.94)
> **Network:** Netbird (100.107.x.x/16)

---

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                          SOURCES                                  │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────────┐              │
│  │ Syslog │ │ Wazuh  │ │ Raw    │ │ Custom       │ │ Delinea PAM │              │
│  │ (UDP)  │ │Webhook │ │ (HTTP) │ │ Integration  │ │ Webhook     │              │
│  └───┬────┘ └───┬────┘ └───┬────┘ └──────┬───────┘ └────────────┘              │
│      └──────────┼──────────┼──────────────┘                     │
│                 │         │         │                           │
│                 ▼         ▼                                      │
│          ┌──────────────────────┐                                │
│          │    soar-node3        │                                │
│          │ (rsyslog forwarder)  │                                │
│          └──────────┬───────────┘                                │
│                     │ Netbird VPN                                │
└─────────────────────┼────────────────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────────────────┐
│                    soar-dashboard (100.107.189.94)               │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │             detection-api (FastAPI, port 8081)           │    │
│  │   ┌────────┐ ┌────────┐ ┌────────┐                     │    │
│  │   │/ingest │ │/process│ │/wazuh  │ │/delinea│  APIRouters  │    │
│  │   └────┬───┘ └────┬───┘ └────┬───┘                     │    │
│  │        └─────┬────┘         │                          │    │
│  │              ▼              ▼                           │    │
│  │   ┌──────────────────────────────┐                     │    │
│  │   │       PARSERS                │                     │    │
│  │   │ Syslog | Raw | Wazuh | Delinea                    │    │
│  │   └──────────────┬───────────────┘                     │    │
│  │                  ▼                                     │    │
│  │   ┌──────────────────────────────┐                     │    │
│  │   │       SERVICES               │                     │    │
│  │   │ Ingestion → Scoring → Anomaly│                    │    │
│  │   └──────────────┬───────────────┘                     │    │
│  │                  ▼                                     │    │
│  │   ┌──────────────────────────────┐                     │    │
│  │   │   REPOSITORIES (Async DB)    │                     │    │
│  │   └──────────────┬───────────────┘                     │    │
│  └─────────────────┼─────────────────────────────────────┘    │
│                    ▼                                          │
│  ┌─────────────────────────────────────────────────────┐     │
│  │          detection-db (TimescaleDB, port 5433)       │     │
│  │  logs_raw | behavior_baselines | anomaly_detections │     │
│  │  risk_scores | entities | scoring_config            │     │
│  └────────────────────┬────────────────────────────────┘     │
│                       ▼                                      │
│  ┌─────────────────────────────────────────────────────┐     │
│  │     detection-dashboard (React, port 8082)           │     │
│  │  Log Viewer | User Detection | Risk | Alerts       │     │
│  └─────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

---

## Container Design

| Container | Image | Port | Base | Scaling |
|:----------|:------|:-----|:-----|:--------|
| `detection-api` | Custom | 8081 | python:3.12-slim | Horizontal |
| `detection-dashboard` | Nginx | 8082 | nginx:alpine | Horizontal |
| `detection-db` | TimescaleDB | 5433 | timescale/timescaledb:latest-pg16 | Vertical |

## Data Flow

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

## Related Docs

| Doc | Path |
|:----|:-----|
| Setup | `docs/SETUP.md` |
| API | `docs/API.md` |
| Database | `docs/DATABASE.md` |

> **Last updated:** 2026-06-23
