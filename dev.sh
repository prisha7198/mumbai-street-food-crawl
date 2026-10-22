#!/usr/bin/env bash
# macOS / Linux: starts backend and frontend together; Ctrl+C stops both.
set -e
cd "$(dirname "$0")"
(cd backend && .venv/bin/python -m uvicorn app.main:app --reload --port 8000) &
(cd frontend && npm run dev) &
trap 'kill 0' INT TERM
wait
