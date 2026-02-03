#!/usr/bin/env bash
set -e

if [ -z "${GOOGLE_API_KEY:-}" ]; then
  echo "GOOGLE_API_KEY is not set. Export it before starting." >&2
  exit 1
fi

export APP_DATA_DIR="${APP_DATA_DIR:-./data}"

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload