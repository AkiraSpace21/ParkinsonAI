#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

if [ ! -f ".deps_installed" ]; then
  pip install --quiet -r backend/requirements.txt
  touch .deps_installed
fi

cd backend
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
