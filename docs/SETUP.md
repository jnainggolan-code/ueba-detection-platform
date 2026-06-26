# 🚀 Setup Guide — UEBA Detection Platform

> Panduan instalasi dan konfigurasi lengkap UEBA Detection Platform
> **Target Server:** `soar-dashboard` (100.107.189.94)
> **Base Path:** `/home/secops/ueba-detection-platform`

---

## 📋 Prerequisites

| Requirement      | Version | Notes                    |
|:-----------------|:--------|:-------------------------|
| Docker           | 24+     | `docker --version`       |
| Docker Compose   | 2.20+   | `docker compose version` |
| Git              | 2.40+   | `git --version`          |
| Python           | 3.12+   | Untuk development API    |
| Node.js          | 20+     | Untuk development Dashboard |
| Netbird          | —       | Wajib untuk koneksi antar-server |

**Akses yang diperlukan:**
- SSH ke `soar-dashboard` (100.107.189.94)
- SSH ke `soar-node3` (100.107.105.81)
- SSH ke `soar-wazuh` (soar-wazuh (100.107.158.164))
- Git access ke `github.com/jnainggolan-code/ueba-detection-platform`

---

## 📁 Directory Structure

Setelah clone, struktur direktori akan seperti ini:

```
ueba-detection-platform/
├── detection-api/              # Python FastAPI (port 8081)
│   ├── app/
│   │   ├── api/v1/endpoints/   # API routers per source
│   │   ├── core/               # Config, security, logging
│   │   ├── parsers/            # Source-specific parsers
│   │   ├── db/repositories/    # Async data access layer
│   │   ├── services/           # Business logic (scoring, anomaly, rule_engine)
│   │   ├── models/             # SQLAlchemy ORM models
│   │   └── main.py             # App entry point
│   ├── alembic/                # DB migrations
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
│
├── detection-dashboard/        # React/TypeScript (port 8082)
│   ├── src/
│   │   ├── components/         # shadcn/ui components
│   │   ├── pages/              # Log Viewer, User Detection, Risk, Alerts
│   │   ├── hooks/              # Custom React hooks
│   │   ├── lib/                # Utilities
│   │   └── App.tsx
│   ├── Dockerfile
│   └── package.json
│
├── detection-db/               # TimescaleDB init scripts
│   ├── init.sql
│   └── 003-rules.sql           # custom_rules table
│
├── deploy/                     # Docker Compose + config
│   ├── docker-compose.yml      # Main compose file (includes Redis + Worker)
│   ├── nginx/                  # Frontend nginx config
│   └── migrations-init/        # Initial DB migrations
│
├── docs/                       # Documentation
│   ├── SETUP.md                # ← You are here
│   ├── API.md
│   ├── DATABASE.md
│   └── ARCHITECTURE.md
│
└── README.md
```

---

## 🐳 1. Setup Container Infrastructure

### 1.1 Clone & Prepare

```bash
# Di soar-dashboard
ssh secops@100.107.189.94

# Clone repo
git clone https://github.com/jnainggolan-code/ueba-detection-platform.git
cd ueba-detection-platform

# Buat environment file
cp .env.example .env
# Edit .env dengan credentials yang sesuai
```

> **⚠️ Catatan:** Credentials di `.env.example` adalah placeholder.
> Ganti semua password sebelum production!

### 1.2 Docker Compose

```bash
docker compose -f deploy/docker-compose.yml up -d
```

Services yang akan jalan:

| Container             | Image                           | Port | Status                         |
|:----------------------|:--------------------------------|:-----|:-------------------------------|
| `detection-db`        | timescale/timescaledb:latest-pg16 | 5433 | PostgreSQL + TimescaleDB       |
| `detection-api`       | detection-api:latest            | 8081 | FastAPI app                    |
| `detection-dashboard` | nginx:alpine                    | 8082 | React SPA                      |

### 1.3 Verify Installation

```bash
# Cek container status
docker ps --filter "name=detection"

# Cek health endpoint
curl http://localhost:8081/api/ueba/health

# Cek dashboard
curl -s -o /dev/null -w "%{http_code}" http://localhost:8082/
```

**Expected output:**
```json
{"status":"ok","module":"UEBA","version":"1.0.0"}
```

---

## 🗄️ 2. Database Setup (TimescaleDB)

### 2.1 Initial Migration

Database migrations dijalankan otomatis saat pertama kali container `detection-db` start.
File SQL di `deploy/migrations-init/` akan di-eksekusi secara berurutan.

**Default tables:**

| Table                 | Type           | Fungsi                          |
|:----------------------|:---------------|:--------------------------------|
| `logs_raw`            | Hypertable     | Semua log masuk (syslog/raw/wazuh) |
| `entities`            | Regular Table  | User & entity profiles          |
| `behavior_baselines`  | Hypertable     | Behavioral baselines & z-scores |
| `anomaly_detections`  | Hypertable     | Triggered anomaly alerts        |
| `risk_scores`         | Hypertable     | Risk score history              |

### 2.2 Manual Migration

```bash
# Masuk ke container DB
docker exec -it detection-db psql -U fraud -d fraud_detection

# Apply migration
\i /docker-entrypoint-initdb.d/002_seed_data.sql
```

### 2.3 Verify Tables

```sql
SELECT hypertable_name, owner, num_chunks
FROM timescaledb_information.hypertables;
```

---

## 🔌 3. API Setup (detection-api)

### 3.1 Endpoint Structure

| Method | Endpoint                | Source       | Fungsi                          |
|:-------|:------------------------|:-------------|:--------------------------------|
| POST   | `/api/v2/ingest`        | soar-node3   | Raw log ingestion               |
| POST   | `/api/v2/process`       | soar-node3   | Annotated/processed data        |
| POST   | `/api/v2/wazuh`         | soar-wazuh   | Wazuh alert webhook             |
| POST   | `/api/v2/ingest`        | soar-node3   | Versi 2 API (scalable)          |
| POST   | `/api/v2/delinea`       | Delinea PAM  | Delinea PAM webhook             |
| POST   | `/api/v2/cortexxdr`      | Cortex XDR   | Cortex XDR alert webhook        |
| GET    | `/api/ueba/health`      | —            | Health check                    |
| GET    | `/api/v1/detections`    | —            | Anomaly detections list         |
| GET    | `/api/v1/users`         | —            | User profiles                   |
| GET    | `/api/v1/users/{id}/risk` | —          | User risk timeline              |

### 3.2 Source Path Separation

Setiap source punya **parser** dan **storage** terpisah:

```
POST /api/v2/ingest  ──► SyslogParser ──► logs_raw (source='syslog')
POST /api/v2/process ──► RawParser    ──► logs_raw (source='raw')
POST /api/v2/wazuh   ──► WazuhParser  ──► logs_raw (source='wazuh')
POST /api/v2/delinea ──► DelineaParser ──► logs_raw (source='delinea')
```

### 3.3 Authentication

API menggunakan API key authentication:

```bash
# Setiap source punya API key berbeda
X-API-Key: syslog-<key>   # Untuk syslog ingestion
X-API-Key: wazuh-<key>    # Untuk Wazuh webhook
X-API-Key: admin-<key>    # Untuk admin endpoints
```

### 3.4 Development mode

```bash
# Local development (hot reload)
cd detection-api
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8081
```

---

## 🎨 4. Dashboard Setup (detection-dashboard)

### 4.1 Dashboard Tabs

| Tab                     | Fitur                                                        |
|:------------------------|:-------------------------------------------------------------|
| 📋 **Log Viewer**       | Virtual-scrolled table, filter by source/level/time          |
| 👤 **User Detection**   | User list with risk score bars, timeline chart               |
| 🔥 **Risk**             | Risk heatmap, top risk entities table                        |
| 🛡️ **Rules**            | Custom Rule Engine — CRUD rules, enable/disable toggle      |
| 🔔 **Alerts**           | Timeline of anomaly detection, severity color coding         |
| 🛡️ **Rules**            | Custom Rule Engine — CRUD rules, enable/disable toggle      |

### 4.2 Development mode

```bash
cd detection-dashboard
npm install
npm run dev
# Local dev server: http://localhost:5173
```

### 4.3 Build for Production

```bash
npm run build
# Output: dist/ → di-serve via nginx di container
```

---

## 📡 5. Pipeline: soar-node3 → soar-dashboard

### 5.1 Network Topology

```
soar-wazuh ──► soar-node3 ──► detection-api (soar-dashboard)
  (syslog)        (:6514)        (:8081/api/v2/ingest)

soar-node3 ──► detection-api (soar-dashboard)
   (raw)         (:8081/api/v2/process)

soar-wazuh ──► detection-api (soar-dashboard)
  (webhook)      (:8081/api/v2/wazuh)

soar-dashboard ──► detection-api (soar-dashboard)
  (delinea)      (:8081/api/v2/delinea)
```

### 5.2 Konfigurasi rsyslog di soar-node3

```bash
# Di soar-node3
ssh secops@100.107.105.81

# Tambah konfigurasi forward
sudo tee /etc/rsyslog.d/40-ueba-forward.conf > /dev/null << 'EOF'
# Forward logs ke detection-api
*.* action(
    type="omfwd"
    target="100.107.189.94"
    port="8081"
    protocol="tcp"
    template="RSYSLOG_SyslogProtocol23Format"
)
EOF

sudo systemctl restart rsyslog
```

### 5.3 Test Pipeline

```bash
# Dari soar-node3, test kirim log
curl -X POST http://100.107.189.94:8081/api/v2/ingest \
  -H "Content-Type: application/json" \
  -d '{"source":"test","message":"Pipeline test","level":"info"}'

# Cek di dashboard: http://100.107.189.94:8082
```

---

## 🚀 6. Deployment (Bind Mount Method)

Sesuai aturan, semua deploy menggunakan **bind mount**, bukan build ulang.

### 6.1 Frontend Update

```bash
# Build di local
cd detection-dashboard
npm run build

# Copy ke server
scp -r dist/* secops@100.107.189.94:~/ueba-detection-platform/detection-dashboard/dist/

# Docker bind mount langsung serve file baru
# Tidak perlu restart container!
```

### 6.2 Backend Update

```bash
# Copy source code ke server
scp -r src/* secops@100.107.189.94:~/ueba-detection-platform/detection-api/src/

# tsx watch auto-restart saat file berubah
# Tidak perlu restart container!
```

### 6.3 Zero-Downtime

```bash
# Scale up sebelum deploy
docker compose up -d --scale detection-api=2 --no-recreate

# Deploy bertahap
# Update satu instance, lalu switch traffic
```

---

## 🛡️ 7. Security

### 7.1 Firewall (UFW)

```bash
# Di soar-dashboard
sudo ufw allow 8081/tcp  # API
sudo ufw allow 8082/tcp  # Dashboard
sudo ufw allow 5433/tcp  # TimescaleDB (hanya dari Netbird)
sudo ufw enable
```

### 7.2 Database Access

```bash
# TimescaleDB hanya accessible via Netbird
# Port 5433 bind ke localhost Netbird interface
```

### 7.3 API Keys

```bash
# Generate API keys
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 🔍 8. Monitoring & Logging

### 8.1 Check Container Logs

```bash
# API logs
docker logs -f detection-api

# DB logs
docker logs detection-db

# All services
docker compose -f deploy/docker-compose.yml logs -f
```

### 8.2 Health Checks

```bash
# API health
curl http://localhost:8081/api/ueba/health

# DB health
docker exec detection-db pg_isready -U fraud -d fraud_detection

# Dashboard
curl -s -o /dev/null -w "%{http_code}" http://localhost:8082/
```

### 8.3 Metrics

```bash
# API metrics (if enabled)
curl http://localhost:8081/api/v1/metrics/prometheus
```

---

## 🐛 9. Troubleshooting

| Masalah                        | Solusi                                                       |
|:-------------------------------|:-------------------------------------------------------------|
| Container `detection-db` unhealthy | Cek `docker logs detection-db`, pastikan volume data tidak corrupt |
| API 404                        | Pastikan endpoint path sesuai dokumentasi API                |
| Dashboard blank                | Cek browser console, pastikan API reachable dari browser     |
| rsyslog not forwarding         | Cek `/var/log/syslog` untuk error rsyslog                    |
| Netbird connection             | `netbird status` untuk cek koneksi peer                      |
| Permission denied              | Pastikan user punya akses ke direktori bind mount            |

### Restart Services

```bash
# Restart semua
docker compose -f deploy/docker-compose.yml restart

# Restart individual
docker restart detection-api
docker restart detection-dashboard
```

### Reset Database

```bash
# Hapus volume database (⚠️ data akan hilang!)
docker compose -f deploy/docker-compose.yml down -v
docker compose -f deploy/docker-compose.yml up -d
```

---

## 📚 Related Documentation

| Doc           | Path                 | Description                      |
|:--------------|:---------------------|:---------------------------------|
| Architecture  | `docs/ARCHITECTURE.md` | System architecture & data flow |
| API Reference | `docs/API.md`        | Complete API documentation       |
| Database      | `docs/DATABASE.md`   | Schema, hypertables, queries     |
| Research      | [Research Repo](https://github.com/jnainggolan-code/research) | UEBA research references |

---

> **Last updated:** 2026-06-23
> **Created by:** Silva Orchestrator
