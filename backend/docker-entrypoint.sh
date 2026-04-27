#!/bin/sh
set -eu

if [ -d "/usr/share/fonts/custom" ]; then
  fc-cache -f /usr/share/fonts/custom >/dev/null 2>&1 || true
fi

exec uvicorn src.main:app --host 0.0.0.0 --port "${APP_PORT:-8000}"
