#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
"$PYTHON" --version
[ -f .env ] || cp .env.example .env
[ -d .venv ] || "$PYTHON" -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
if [ "${MEDRAY_INSTALL_OPTIONAL:-0}" = "1" ]; then
  echo "Installing optional model dependencies..."
  python -m pip install -r backend/requirements-optional.txt
fi
node --version
node -e "const [a,b]=process.versions.node.split('.').map(Number); if (!((a===22 && b>=12)||a>=24)) { console.error('Install Node 22.12+ or 24 LTS.'); process.exit(1); }"
npm --version
export npm_config_cache="$ROOT/data/cache/npm"
mkdir -p "$npm_config_cache"
(cd frontend && npm ci)
command -v ollama >/dev/null && echo "Ollama found." || echo "Ollama is not installed; the built-in mode remains available."
echo "Setup complete. Run ./start_medray_v2.sh"
