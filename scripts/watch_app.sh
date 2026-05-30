#!/usr/bin/env bash
# watch_app.sh — restart the PS5-MIDI-Bridge app whenever any .py file in src/ changes.
# Pure bash + stat polling, no dependencies. Press Ctrl-C to stop.
#
# Usage:
#   bash scripts/watch_app.sh
#   GMB_NO_3D=1 bash scripts/watch_app.sh   # faster startup, skip Three.js
set -u
cd "$(dirname "$0")/.."
. .venv/bin/activate 2>/dev/null || true

POLL_INTERVAL="${POLL_INTERVAL:-1}"
APP_PID=""

# Build the mtime fingerprint of every .py file under src/.
fingerprint() {
    find src -type f \( -name "*.py" -o -name "*.qss" \) -exec stat -f "%m %N" {} \; 2>/dev/null | sort | shasum | awk '{print $1}'
}

# Start the app in the background, capture its PID.
start_app() {
    echo ""
    echo "▶  $(date +%H:%M:%S)  launching app…"
    python -m gamepad_midi_bridge 2>&1 | sed -u 's/^/   │ /' &
    APP_PID=$!
}

# Politely SIGTERM, then escalate to SIGKILL if needed.
stop_app() {
    if [ -n "$APP_PID" ] && kill -0 "$APP_PID" 2>/dev/null; then
        echo "■  $(date +%H:%M:%S)  stopping pid=$APP_PID…"
        kill "$APP_PID" 2>/dev/null
        for _ in 1 2 3; do
            kill -0 "$APP_PID" 2>/dev/null || break
            sleep 0.3
        done
        kill -9 "$APP_PID" 2>/dev/null || true
        wait "$APP_PID" 2>/dev/null || true
    fi
    APP_PID=""
}

cleanup() {
    echo ""
    echo "✗  watcher exiting, killing app…"
    stop_app
    exit 0
}
trap cleanup INT TERM EXIT

echo "👀  watching src/ for .py/.qss changes — Ctrl-C to stop"
PREV=$(fingerprint)
start_app

while true; do
    sleep "$POLL_INTERVAL"
    CURR=$(fingerprint)
    if [ "$CURR" != "$PREV" ]; then
        echo "↻  $(date +%H:%M:%S)  change detected — restarting"
        stop_app
        sleep 0.2
        start_app
        PREV="$CURR"
    fi
done
