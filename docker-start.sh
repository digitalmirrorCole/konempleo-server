#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Starting KonEmpleo Server..."
echo "CWD=$(pwd)"
echo "PYTHONPATH=${PYTHONPATH:-}"
echo "Listing /konempleo contents:"
ls -la /konempleo || true

# Si la app necesita migraciones de base de datos (opcional):
# echo "📦 Running Alembic migrations..."
# alembic upgrade head || echo "Alembic not found, skipping migrations."

# Ejecutar la aplicación FastAPI
echo "🟢 Launching FastAPI with Uvicorn..."
exec python -m uvicorn --app-dir /konempleo app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
