#!/usr/bin/env bash
set -euo pipefail

# Opcional: imprime diagnóstico útil
echo "CWD=$(pwd)"
echo "PYTHONPATH=${PYTHONPATH:-}"
echo "Listing /konempleo:"
ls -la /konempleo || true

# Lanza Uvicorn apuntando a /konempleo y al módulo app.main:app
exec python -m uvicorn --app-dir /konempleo app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
