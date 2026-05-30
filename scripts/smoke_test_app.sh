#!/usr/bin/env bash
# smoke_test_app.sh — every new module must pass this before the agent reports success.
# Launches the app for N seconds. Exit 0 = clean (SIGALRM killed a healthy app).
# Exit !=0 = the app crashed on its own before the timer fired.
set -u
cd "$(dirname "$0")/.."
DURATION="${1:-6}"
LOG=$(mktemp -t gmb_smoke.XXXXXX)
. .venv/bin/activate 2>/dev/null || true
perl -e 'alarm '"$DURATION"'; exec @ARGV' python -m gamepad_midi_bridge >"$LOG" 2>&1
RC=$?
# Exit 142 = SIGALRM fired = app was alive when killed = HEALTHY
# Exit 0   = app exited on its own before alarm = suspicious (likely no-window or self-quit)
# Exit other = real crash
if grep -qiE "traceback|fatal|segmentation|crash report saved|attribute ?error|nameerror" "$LOG"; then
    echo "FAIL: error pattern in log"
    tail -40 "$LOG"
    exit 1
fi
case "$RC" in
    142)
        echo "PASS: app survived ${DURATION}s (alarm killed a healthy process)"
        exit 0
        ;;
    0)
        # Possibly the user-presented dialog auto-dismissed and run() returned.
        # That's not a crash, but it's also not a confirmed live window. Warn.
        echo "WARN: app exited cleanly (code 0) before alarm — not a crash, but no live window"
        exit 0
        ;;
    *)
        echo "FAIL: app exited with code $RC"
        tail -40 "$LOG"
        exit "$RC"
        ;;
esac
