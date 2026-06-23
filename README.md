# 🛡️ UEBA Detection Platform

> **User and Entity Behavior Analytics** — Enterprise-scale anomaly detection platform
> Built with FastAPI (Python), TimescaleDB, and React Dashboard

## 🏗 Architecture

```
soar-node3 ──► detection-api (:8081) ←── source-path separation
                    │                        /api/v2/ingest  (raw data)
                    │                        /api/v2/process (annotated)
                    │                        /api/v2/wazuh  (wazuh format)
                    │
             detection-dashboard (:8082) ← UI (React)
                    │
             detection-db (:5433) ← TimescaleDB
```

## 📦 Container Prefix: `detection_xxx`

- `detection-api` — Python FastAPI (port 8081)
- `detection-dashboard` — React/TypeScript (port 8082)
- `detection-db` — TimescaleDB (port 5433)

## 🔄 SDLC Flow

```
Request → Issue → Branch → Code → Push → PR → Merge → Deploy
```

## 📚 Documentation

- [Architecture](./docs/ARCHITECTURE.md)
- [API Reference](./docs/API.md)
- [Database Schema](./docs/DATABASE.md)
- [Setup Guide](./docs/SETUP.md)

## 🚀 Tech Stack

| Layer | Tech |
|:------|:------|
| API | Python FastAPI 3.12+ |
| Database | TimescaleDB (PostgreSQL 16) |
| Dashboard | React 18 + TypeScript |
| Container | Docker + docker-compose |
| Deploy | Bind mount to soar-dashboard |
