#!/bin/bash
set -e

echo "=== Starting PharmaRAG Single-Container Deployment ==="

# Set default ports and hostnames
export PORT=${PORT:-8000}
export BACKEND_URL=${BACKEND_URL:-"http://127.0.0.1:8000"}
export HOSTNAME="0.0.0.0"

# 1. Start FastAPI backend
echo "[1/2] Starting FastAPI backend on port 8000..."
cd /app/backend
uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# 2. Start Next.js frontend
echo "[2/2] Starting Next.js frontend on port 3000..."
cd /app/frontend
PORT=3000 npm run start &
FRONTEND_PID=$!

# Graceful termination handler
cleanup() {
  echo "Received termination signal. Shutting down services..."
  kill -TERM "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  echo "All services stopped."
  exit 0
}

trap cleanup SIGINT SIGTERM

echo "PharmaRAG services are running (Backend: :8000, Frontend: :3000)."

# Wait for any process to exit
wait -n "$BACKEND_PID" "$FRONTEND_PID"
