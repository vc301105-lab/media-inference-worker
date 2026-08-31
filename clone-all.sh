#!/usr/bin/env bash
#
# 🚀 clone-all.sh — One-click clone of the world's best media-AI repos
# Higgsfield · Runway · Midjourney · Sora · Kling · ElevenLabs (+ alternatives)
#
# Usage:
#   ./clone-all.sh          # clone every repo into ./repos/
#   ./clone-all.sh runway   # only repos whose path contains "runway" (case-insensitive)
#   ./clone-all.sh elevenlabs kling
#
# Uses shallow clones (--depth 1) to keep downloads fast and small.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOS_FILE="$SCRIPT_DIR/repos.txt"
TARGET_DIR="${MEDIA_REPOS_DIR:-$SCRIPT_DIR/repos}"

if ! command -v git >/dev/null 2>&1; then
    echo "❌ git not found. Install it first: sudo apt install git" >&2
    exit 1
fi
if [[ ! -f "$REPOS_FILE" ]]; then
    echo "❌ repos.txt not found next to clone-all.sh" >&2
    exit 1
fi

mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

mapfile -t FILTERS < <(printf '%s\n' "${@:1}" | tr '[:upper:]' '[:lower:]')

TOTAL=0
SKIPPED=0
CLONED=0
FAILED=0

while IFS= read -r line; do
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

    url="${line%%[[:space:]]*}"
    name="$(basename "$url" .git)"
    lower="$(printf '%s' "$url $name" | tr '[:upper:]' '[:lower:]')"

    # Apply optional filters
    if [[ ${#FILTERS[@]} -gt 0 ]]; then
        match=0
        for f in "${FILTERS[@]}"; do
            [[ "$lower" == *"$f"* ]] && match=1 && break
        done
        [[ $match -eq 1 ]] || continue
    fi

    TOTAL=$((TOTAL + 1))

    if [[ -d "$name/.git" ]]; then
        echo "⏭  SKIP    $name (already exists)"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    echo "📦 CLONE   $name"
    if git clone --depth 1 --single-branch "$url" "$name" >/dev/null 2>&1; then
        CLONED=$((CLONED + 1))
    else
        echo "❌ FAILED  $name"
        FAILED=$((FAILED + 1))
    fi
done < "$REPOS_FILE"

echo
echo "──────────────────────────────────────────────"
echo "  Selected repos : $TOTAL"
echo "  Cloned         : $CLONED"
echo "  Already existed: $SKIPPED"
echo "  Failed         : $FAILED"
echo "  Location       : $TARGET_DIR"
echo "──────────────────────────────────────────────"

[[ $FAILED -eq 0 ]] || exit 1
