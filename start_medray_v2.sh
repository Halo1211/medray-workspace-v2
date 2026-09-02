#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] || cp .env.example .env
[ -d .venv ] || bash scripts/setup_unix.sh
[ -d frontend/node_modules ] || bash scripts/setup_unix.sh
. .venv/bin/activate

BACKEND_HOST="${MEDRAY_HOST:-127.0.0.1}"
case "$BACKEND_HOST" in
  127.0.0.1|localhost) ;;
  *) echo "Without authentication, the MedRay backend may bind only to loopback: MEDRAY_HOST=$BACKEND_HOST" >&2; exit 1 ;;
esac
BACKEND_PORT="$(python - "${MEDRAY_PORT:-8765}" "$BACKEND_HOST" <<'PY'
import socket
import sys

start = int(sys.argv[1])
host = sys.argv[2]
for port in range(start, start + 50):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            continue
        print(port)
        break
else:
    raise SystemExit("No free backend port was found.")
PY
)"
export VITE_API_BASE="http://${BACKEND_HOST}:${BACKEND_PORT}/api"

PYTHONPATH=backend python -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
BACKEND_PID=$!
(cd frontend && npm run dev -- --host 127.0.0.1 --port 5173) &
FRONTEND_PID=$!
echo "MedRay v2: http://127.0.0.1:5173"
echo "Backend: ${VITE_API_BASE}/health"
trap 'kill $BACKEND_PID $FRONTEND_PID' INT TERM EXIT
wait
