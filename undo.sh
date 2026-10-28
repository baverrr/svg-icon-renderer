#!/bin/bash
# Undoes install.sh: Qt goes back to its own SVG renderer (QtSvg) at your next login.
# Works from a text console (Ctrl+Alt+F3) if Plasma ever fails to start with the plugin.
# Run: bash undo.sh
set -euo pipefail

rm -f "$HOME/.config/plasma-workspace/env/rsvg-qt-icons.sh"
rm -rf "$HOME/.local/lib/rsvg-qt-icons"
rm -f "$HOME/.cache/icon-cache.kcache"

echo "Removed. Log out and back in to switch Plasma back to QtSvg."
