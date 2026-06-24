# =============================================================================
# detection-db — TimescaleDB 16
# Container: TimescaleDB 2.x on PostgreSQL 16
# Port:      5433
# =============================================================================

FROM timescale/timescaledb:latest-pg16

# Copy initialization scripts
# init.sql akan di-execute otomatis oleh TimescaleDB saat container pertama kali start
COPY init.sql /docker-entrypoint-initdb.d/01-init.sql
COPY functions.sql /docker-entrypoint-initdb.d/02-functions.sql

# Expose PostgreSQL default port
EXPOSE 5432

# Default command
CMD ["postgres"]

# Note: Environment variables (POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD)
# harus diset via .env file atau docker-compose.
