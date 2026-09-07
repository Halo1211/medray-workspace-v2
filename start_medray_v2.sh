#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] || cp .env.example .env
[ -f .venv/bin/python ] && [ -d frontend/node_modules ] || bash scripts/setup_unix.sh
exec .venv/bin/python scripts/launch.py "$@"
