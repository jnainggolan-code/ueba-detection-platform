# 🔌 API Reference — UEBA Detection Platform

> **Base URL:** `http://100.107.189.94:8081`
> **Swagger UI:** `http://100.107.189.94:8081/docs`

---

## Authentication

### API Keys

| Source | Header | Scope |
|:-------|:-------|:------|
| Syslog | `X-API-Key: ***` | `ingest:syslog` |
| Raw Log | `X-API-Key: ***` | `ingest:raw` |
| Wazuh | `X-API-Key: ***` | `ingest:wazuh` |
| Delinea | `X-API-Key: ***` | `ingest:delinea` |
| Cortex XDR | `X-API-Key: ***` | `ingest:cortex_xdr` |
| Admin | `X-API-Key: ***` | `admin:*` |

### JWT Tokens

```bash
curl -X POST http://100.107.189.94:8081/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"***"}'
```

---

## Source Path Separation

```
POST /api/v2/ingest   → SyslogParser → logs_raw (source='syslog')
POST /api/v2/process  → RawParser    → logs_raw (source='raw')
POST /api/v2/wazuh    → WazuhParser  → logs_raw (source='wazuh')
POST /api/v2/delinea  → DelineaParser → logs_raw (source='delinea')
POST /api/v2/cortexxdr → CortexXDRParser → logs_raw (source='cortex_xdr')
```

---

## Endpoints

### Ingestion

#### POST `/api/v2/ingest`
```bash
curl -X POST http://100.107.189.94:8081/api/v2/ingest \
  -H "X-API-Key: ***" -H "Content-Type: application/json" \
  -d '{"timestamp":"2026-06-23T08:00:00Z","hostname":"soar-node3",
       "source":"auth.log","log_level":"info",
       "message":"Accepted publickey for jnainggolan"}'
```

#### POST `/api/v2/process`
```bash
curl -X POST http://100.107.189.94:8081/api/v2/process \
  -H "X-API-Key: ***" -H "Content-Type: application/json" \
  -d '{"timestamp":"...","entity_type":"user","entity_value":"jnainggolan",
       "event_type":"login","source_ip":"100.107.105.81","status":"success"}'
```

#### POST `/api/v2/delinea`

#### POST `/api/v2/delinea`
Webhook untuk Delinea PAM events (privileged account access, password checkout, session recording events).

#### POST `/api/v2/cortexxdr`
Webhook untuk Palo Alto Cortex XDR alerts (malware, BIOC, correlation alerts).

```bash
curl -X POST http://100.107.189.94:8081/api/v2/cortexxdr \
  -H "X-API-Key: ***" -H "Content-Type: application/json" \
  -d '{"alert_id":"XDR12345","alert_type":"malware","severity":"high",
       "endpoint_name":"WIN-SRV-01","user":"jnainggolan",
       "file_name":"ransomware.exe","action":"blocked"}'
```

```bash
curl -X POST http://100.107.189.94:8081/api/v2/delinea \
  -H "X-API-Key: ***" -H "Content-Type: application/json" \
  -d '{"event_type":"password_checkout","timestamp":"2026-06-23T08:00:00Z",
       "user":"admin","account":"root@server01","target":"192.168.1.100",
       "reason":"emergency_access","approver":"manager@company.com"}'
```

#### POST `/api/v2/wazuh`
```bash
curl -X POST http://100.107.189.94:8081/api/v2/wazuh \
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

### Custom Rules (Rule Engine)

#### POST `/api/v1/rules`
Create a new detection rule.

```bash
curl -X POST http://100.107.189.94:8081/api/v1/rules   -H "Content-Type: application/json" \
  -d '{
    "name": "Suspicious Login",
    "description": "Detect high-risk logins",
    "conditions": {
      "logic": "AND",
      "conditions": [
        {"field": "event_type", "operator": "equals", "value": "windows_4624"},
        {"field": "is_anomaly", "operator": "equals", "value": true}
      ]
    },
    "action": {
      "type": "create_alert",
      "severity": "high",
      "title": "Suspicious Login Detected",
      "description": "Rule engine triggered alert"
    },
    "enabled": true,
    "priority": 10
  }'
```

#### GET `/api/v1/rules`
List all rules (paginated).

**Query params:** `page`, `limit`, `enabled`

#### GET `/api/v1/rules/{rule_id}`
Get single rule details.

#### PUT `/api/v1/rules/{rule_id}`
Update rule (partial). Toggle `enabled` to activate/deactivate.

```bash
curl -X PUT http://100.107.189.94:8081/api/v1/rules/1 \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

#### DELETE `/api/v1/rules/{rule_id}`
Delete a rule permanently.

### Supported Condition Operators
| Operator | Description |
|:---------|:------------|
| `equals` | Field equals value |
| `not_equals` | Field does not equal value |
| `contains` | Value contains substring |
| `greater_than` | Numeric field > value |
| `less_than` | Numeric field < value |
| `in_list` | Field in list of values |
| `not_in_list` | Field not in list |
| `matches_regex` | Field matches regex |

### Available Condition Fields
| Field | Source |
|:------|:-------|
| `event_type` | `parsed_data.event_type` |
| `source` | Direct event field |
| `source_ip` | Direct event field |
| `log_level` | Direct event field |
| `risk_score` | From risk scoring result |
| `risk_level` | From risk scoring result |
| `is_anomaly` | From risk scoring result |
| `entity` | From parsed data |

---

### Engine Pipeline

Pipeline dijalankan oleh **RQ Worker** untuk setiap event yang masuk:

```
Event Ingestion
  -> Enqueue ke Redis Queue (engine-pipeline)
  -> RQ Worker consume
  -> Anomaly Detection (z-score)
  -> Risk Scoring (decay + weight)
  -> Rule Engine (evaluate custom rules)
  -> Commit to DB
```

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
- **Wazuh** → `http://100.107.189.94:8081/api/v2/wazuh`
- **Delinea PAM** → `http://100.107.189.94:8081/api/v2/delinea`
- **Cortex XDR** → `http://100.107.189.94:8081/api/v2/cortexxdr`


## Related Docs

| Doc | Path |
|:----|:-----|
| Setup | `docs/SETUP.md` |
| Database | `docs/DATABASE.md` |
| Architecture | `docs/ARCHITECTURE.md` |

> **Last updated:** 2026-06-23
