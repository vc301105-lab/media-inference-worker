#!/usr/bin/env bash
# ⚙️ AI Film Studio — one-time setup
set -euo pipefail
cd "$(dirname "$0")"

echo "🎬 AI Film Studio setup"
echo "────────────────────────"
if [[ ! -d .venv ]]; then
    echo "→ Creating virtualenv…"
    python3 -m venv .venv
fi
echo "→ Installing dependencies…"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet requests pillow imageio-ffmpeg
echo "→ Optional: edge-tts for free voiceover…"
.venv/bin/pip install --quiet edge-tts || echo "   (skipped)"

echo "→ MCP server (AI agents: Claude Desktop / Cursor)…"
.venv/bin/pip install --quiet "mcp<2" || echo "   (skipped — MCP optional)"

echo
echo "✅ Setup complete!"
echo "   Web UI  : ./start_studio.sh                    → http://localhost:8080"
echo "   CLI     : .venv/bin/python -m film_studio status"
echo "   Film    : .venv/bin/python -m film_studio all \"My First Film\" --genre scifi"
echo "   MCP     : .venv/bin/python -m film_studio.mcp_server   (connect in Claude/Cursor)"
