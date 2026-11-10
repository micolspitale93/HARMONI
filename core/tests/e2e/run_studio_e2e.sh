#!/bin/bash
# Usage: core/tests/e2e/run_studio_e2e.sh [screenshots dir]
# Needs node and Playwright with Chromium (npm install playwright && npx playwright install chromium).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
WORK="$(mktemp -d)"
SHOTS="${1:-$WORK/screenshots}"
PORT="${STUDIO_PORT:-8811}"
mkdir -p "$WORK/core" "$WORK/ros2" "$SHOTS"
cp -r "$REPO/core/trees" "$WORK/core/trees"
cp -r "$REPO/ros2/config" "$WORK/ros2/config"
PYTHONPATH="$REPO/core" python3 -m harmoni.studio --root "$WORK" --port "$PORT" > "$WORK/studio.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null; rm -rf "$WORK"' EXIT
for _ in $(seq 1 50); do curl -sf "http://127.0.0.1:$PORT/api/info" >/dev/null && break; sleep 0.2; done
export NODE_PATH="$(npm root -g 2>/dev/null):${NODE_PATH:-}"   # a globally installed Playwright
STUDIO_URL="http://127.0.0.1:$PORT" node "$HERE/studio.e2e.js" "$SHOTS"
