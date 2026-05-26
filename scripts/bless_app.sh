#!/usr/bin/env bash
# Remove macOS Gatekeeper's quarantine flag from the unsigned .app so it can
# launch without the "from an unknown developer" sheet. Until we wire up
# codesigning + notarization, this is the one-time per-machine workaround.
#
# Run once after downloading: ./scripts/bless_app.sh
#
# This isn't a security bypass — it's the same thing macOS does after you
# click "Open Anyway" in System Settings. Saves the trip through the dialog.
set -euo pipefail

APP="${1:-dist/Gamepad MIDI Bridge.app}"

if [ ! -d "$APP" ]; then
    echo "App not found at: $APP"
    echo "Usage: $0 [path/to/Gamepad MIDI Bridge.app]"
    exit 1
fi

echo "Removing com.apple.quarantine from $APP ..."
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true
echo "Done. You can now double-click to open."
