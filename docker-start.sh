#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Starting KonEmpleo Backend"
echo "CWD=$(pwd)"
echo "PYTHONPATH=${PYTHONPATH:-<empty>}"

# Asegura que Python vea el paquete "app" dentro de /konempleo
export PYTHONPATH="/konempleo:${PYTHONPATH:-}"

# Lanza FastAPI con Gunicorn+Uvicorn
exec gunicorn app.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 2 \
  --bind 0.0.0.0:${PORT:-8000} \
  --timeout 120
