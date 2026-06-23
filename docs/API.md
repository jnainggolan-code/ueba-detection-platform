# 🔌 API Reference — UEBA Detection Platform

> **Base URL:** `http://dashboard.netbird.cloud:8081`
> **Swagger UI:** `http://dashboard.netbird.cloud:8081/docs`

---

## Authentication

### API Keys

| Source | Header | Scope |
|:-------|:-------|:------|
| Syslog | `X-API-Key: ***` | `ingest:syslog` |
| Raw Log | `X-API-Key: ***` | `ingest:raw` |
| Wazuh | `X-API-Key: ***` | `ingest:wazuh` |
| Delinea | `X-API-Key: ***` | `ingest:delinea` |
| Admin | `X-API-Key: ***` | `admin:*` |

### JWT Tokens

```bash
curl -X POST http://dashboard.netbird.cloud:8081/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"***"}'
```

---

## Source Path Separation

```
POST /api/v1/ingest   → SyslogParser → logs_raw (source='syslog')
POST /api/v1/process  → RawParser    → logs_raw (source='raw')
POST /api/v1/wazuh    → WazuhParser  → logs_raw (source='wazuh')
POST /api/v1/delinea  → DelineaParser → logs_raw (source='delinea')
```

---

## Endpoints

### Ingestion

#### POST `/api/v1/ingest`
```bash
curl -X POST http://dashboard.netbird.cloud:8081/api/v1/ingest \
  -H "X-API-Key: ***" -H "Content-Type: application/json" \
  -d '{"timestamp":"2026-06-23T08:00:00Z","hostname":"soar-node3",
       "source":"auth.log","log_level":"info",
       "message":"Accepted publickey for jnainggolan"}'
```

#### POST `/api/v1/process`
```bash
curl -X POST http://dashboard.netbird.cloud:8081/api/v1/process \
  -H "X-API-Key: ***" -H "Content-Type: application/json" \
  -d '{"timestamp":"...","entity_type":"user","entity_value":"jnainggolan",
       "event_type":"login","source_ip":"100.107.105.81","status":"success"}'
```

#### POST `/api/v1/delinea`

#### POST `/api/v1/delinea`
Webhook untuk Delinea PAM events (privileged account access, password checkout, session recording events).

```bash
curl -X POST http://dashboard.netbird.cloud:8081/api/v1/delinea \
  -H "X-API-Key: ***" -H "Content-Type: application/json" \
  -d '{"event_type":"password_checkout","timestamp":"2026-06-23T08:00:00Z",
       "user":"admin","account":"root@server01","target":"192.168.1.100",
       "reason":"emergency_access","approver":"manager@company.com"}'
```

#### POST `/api/v1/wazuh`
```bash
curl -X POST http://dashboard.netbird.cloud:8081/api/v1/wazuh \
  -H "X-API-Key: ***" -H "Content-Type: application/json" \
  -d '{"timestamp":"...","rule_id":5710,"rule_description":"sshd: Failed password",
       "severity":10,"data":{"srcip":"45.33.32.156","dstuser":"root"},
       "mitre":{"technique_id":"T1110","technique_name":"Brute Force"}}'
```

### Detections

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| GET | `/api/v1/detections` | List anomalies |
| GET | `/api/v1/detections/{id}` | Detail detection |
| PATCH | `/api/v1/detections/{id}` | Update status |

**Query params:** `status`, `severity`, `anomaly_type`, `entity_id`, `from`, `to`, `limit`, `offset`

### Entities/Users

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| GET | `/api/v1/users` | List entities |
| GET | `/api/v1/users/{id}` | User detail |
| GET | `/api/v1/users/{id}/risk` | Risk timeline |
| GET | `/api/v1/users/{id}/timeline` | Activity timeline |
| GET | `/api/v1/users/{id}/factors` | Risk factors |

### Dashboard

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| GET | `/api/v1/dashboard/summary` | Summary cards |
| GET | `/api/v1/dashboard/alerts` | Alert timeline |
| GET | `/api/v1/dashboard/risk-leaderboard` | Top risk |
| GET | `/api/v1/dashboard/heatmap` | Risk heatmap |
| GET | `/api/v1/dashboard/credential-flow` | Cred flow |
| GET | `/api/v1/dashboard/db-summary` | DB stats |
| GET | `/api/v1/dashboard/server-anomaly` | Server anomaly |

### UEBA Engine

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| GET | `/api/ueba/health` | Health check |
| GET | `/api/ueba/risk/current` | Risk levels |
| GET | `/api/ueba/risk/user/{username}` | User risk |
| GET | `/api/ueba/events/user/{username}` | User events |
| GET | `/api/ueba/peer-group/{username}` | Peer group |
| GET | `/api/ueba/detections` | UEBA detections |

### Reports

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| POST | `/api/v1/reports/generate` | Generate report |
| GET | `/api/v1/reports/{id}/download` | Download |

---

## Error Codes

| Code | Description |
|:-----|:------------|
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 422 | Validation Error |
| 429 | Rate Limit |
| 500 | Internal Error |

---

## Related Docs

| Doc | Path |
|:----|:-----|
| Setup | `docs/SETUP.md` |
| Database | `docs/DATABASE.md` |
| Architecture | `docs/ARCHITECTURE.md` |

> **Last updated:** 2026-06-23
