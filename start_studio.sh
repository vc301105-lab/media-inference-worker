#!/usr/bin/env bash
# 🎬 Start the AI Film Studio web UI (browser dashboard)
# Usage: ./start_studio.sh [port]
set -euo pipefail
cd "$(dirname "$0")"

PORT="${1:-8080}"

if [[ ! -x .venv/bin/python ]]; then
    echo "❌ Setup first: ./setup_studio.sh"
    exit 1
fi

echo "🎬 Starting AI Film Studio → http://localhost:$PORT"
exec .venv/bin/python -m film_studio.web --host 0.0.0.0 --port "$PORT"
