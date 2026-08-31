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

echo
echo "✅ Setup complete!"
echo "   Run: .venv/bin/python -m film_studio status"
echo "   Make a film: .venv/bin/python -m film_studio all \"My First Film\" --genre scifi"
