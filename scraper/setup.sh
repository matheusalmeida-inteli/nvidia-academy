#!/bin/bash
# Setup script for NVIDIA Radar scraper environment
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PIXI_BIN="${PROJECT_DIR}/.pixi/envs/default/bin"

echo "=== NVIDIA Radar Setup ==="

# 1. Start Postgres (from pixi environment)
echo "[1/5] Starting PostgreSQL..."
mkdir -p "${PROJECT_DIR}/pg_data"
if [ ! -f "${PROJECT_DIR}/pg_data/PG_VERSION" ]; then
    "${PIXI_BIN}/initdb" -D "${PROJECT_DIR}/pg_data" -U nvidia_radar -W
fi

# Configure trust auth
if ! grep -q "host all all 127.0.0.1/32 trust" "${PROJECT_DIR}/pg_data/pg_hba.conf" 2>/dev/null; then
    echo "host all all 127.0.0.1/32 trust" >> "${PROJECT_DIR}/pg_data/pg_hba.conf"
    echo "local all all trust" >> "${PROJECT_DIR}/pg_data/pg_hba.conf"
fi

"${PIXI_BIN}/pg_ctl" -D "${PROJECT_DIR}/pg_data" -l "${PROJECT_DIR}/postgres.log" start -w -t 30

# 2. Create database
echo "[2/5] Creating database..."
"${PIXI_BIN}/psql" -U nvidia_radar -h 127.0.0.1 -d postgres -c "CREATE DATABASE nvidia_radar;" 2>/dev/null || true
"${PIXI_BIN}/psql" -U nvidia_radar -h 127.0.0.1 -d nvidia_radar -f "${PROJECT_DIR}/schema.sql"

# 3. Run scraper
echo "[3/5] Running scraper..."
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT=5432
export POSTGRES_USER=nvidia_radar
export POSTGRES_PASSWORD=nvidia_radar_pass
export POSTGRES_DB=nvidia_radar

echo "  WOW (99 startups)..."
"${PIXI_BIN}/python" -m scraper.run --source wow --output postgres

echo "[4/5] DB stats..."
"${PIXI_BIN}/python" -m scraper.run --stats

echo "[5/5] Done!"
echo ""
echo "Run: export POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5432 POSTGRES_USER=nvidia_radar POSTGRES_PASSWORD=nvidia_radar_pass POSTGRES_DB=nvidia_radar"
echo "Then: ${PIXI_BIN}/python -m scraper.run --help"
