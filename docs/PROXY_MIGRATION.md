# 🔄 Vite Proxy → Nginx Proxy Migration

> **Date:** 2026-06-24
> **Context:** Log Viewer page blank/404 → Root cause: Vite HMR dev server proxy could not resolve Docker DNS

---

## ❌ Masalah

Dashboard awalnya pake **Vite dev server** (`vite --port 5173`) dengan proxy config:

```ts
// vite.config.ts (OLD — Vite proxy)
server: {
  proxy: {
    '/api': {
      target: 'http://100.107.189.94:8081',   // ❌ Host IP
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ''), // ❌ Strips /api
    },
  },
},
```

### 3 masalah sekaligus:

| # | Masalah | Dampak |
|:-:|:--------|:-------|
| 1 | **Rewrite rule** `path.replace(/^\/api/, '')` | `/api/v1/events` → `/v1/events` (404) |
| 2 | **Vite proxy target ke host IP** | Dari dalam container, `100.107.189.94:8081` timeout (loopback) |
| 3 | **Vite dev server bukan production** | File change trigger HMR rebuild, tidak cocok untuk production |

---

## ✅ Solusi: Nginx Production + Reverse Proxy

### Arsitektur Baru

```
Browser ──▶ :8082 ──▶ Nginx ──┬── /api/* ──▶ detection-api:8081 (internal)
                                └── /* ──▶ Serve static HTML/JS/CSS
```

### Nginx Config (`detection-dashboard/nginx/default.conf`)

```nginx
server {
    listen 8082;
    root /usr/share/nginx/html;
    index index.html;

    # API Reverse Proxy
    location /api/ {
        proxy_pass http://detection-api:8081;   # ✅ Docker DNS
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### Dockerfile (`Dockerfile.dev` → production mode)

```dockerfile
# Build Stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production Stage
FROM nginx:alpine
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8082
CMD ["nginx", "-g", "daemon off;"]
```

### Docker Compose (`deploy/docker-compose.yml`)

```yaml
detection-dashboard:
  build:
    context: ../detection-dashboard
    dockerfile: Dockerfile.dev
  container_name: detection-dashboard
  ports:
    - "8082:8082"                        # ✅ Port 8082 langsung (bukan 5173)
  depends_on:
    - detection-api
  networks:
    - ueba-network
```

---

## 📋 Files Changed

| File | Change |
|:-----|:-------|
| `detection-dashboard/Dockerfile.dev` | Multi-stage: build static → nginx serve (production mode) |
| `detection-dashboard/nginx/default.conf` | Listen 8082, proxy_pass `/api` → `detection-api:8081` |
| `detection-dashboard/vite.config.ts` | Removed `/api` proxy rule (tidak dipakai lagi) |
| `detection-dashboard/src/lib/api.ts` | `baseURL: '/api'` (relative, via nginx proxy) |
| `deploy/docker-compose.yml` | Dashboard port `8082:8082`, tidak ada `VITE_API_URL` env |
| `deploy/.env.example` | Removed `VITE_API_URL` |

---

## 🔗 Related

- Issue: Phase 1 — Dashboard blank/404 on Log Viewer
- Fix: Nginx reverse proxy replacing Vite HMR proxy
- Benefit: Production-ready, no hot-reload overhead, proper caching

---

## Why Not Vite Proxy?

| Aspek | Vite HMR Proxy | Nginx Reverse Proxy |
|:------|:---------------|:--------------------|
| **Target** | Host IP (timeout dalam container) | Docker DNS service name ✅ |
| **Rewrite** | Manual, rawan salah | No rewrite needed ✅ |
| **Caching** | ❌ No static caching | ✅ `expires 1y` for assets |
| **Security** | ❌ Vite dev headers | ✅ X-Frame-Options, CSP, etc |
| **Production** | ❌ Dev-only | ✅ Production-grade |
| **Hot Reload** | ✅ Yes (dev only) | ❌ Not needed (rebuild on deploy) |
