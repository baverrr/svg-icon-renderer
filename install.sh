#!/bin/bash
# Makes Qt apps in your Plasma session draw SVG icons with librsvg (full filters) instead of QtSvg.
# Everything goes under your home folder; no sudo. Build first with build.sh.
# Takes effect at your next Plasma login. Undo with undo.sh (it works from a text console too).
# Run: bash install.sh
set -euo pipefail
here=$(dirname "$(readlink -f "$0")")
plugin="$here/build/imageformats/librsvgqt.so"
dest="$HOME/.local/lib/rsvg-qt-icons/plugins"
envdir="$HOME/.config/plasma-workspace/env"
envfile="$envdir/rsvg-qt-icons.sh"

[ "$(id -u)" != 0 ] || { echo "Run this as yourself, not with sudo."; exit 1; }
[ -f "$plugin" ] || { echo "No plugin yet. Run build.sh first."; exit 1; }

# 1. copy the plugin into its own plugin folder
install -D -m 644 "$plugin" "$dest/imageformats/librsvgqt.so"

# 2. put that folder first on QT_PLUGIN_PATH for the Plasma session. startplasma sources this
#    folder at login, so plasmashell and every app it launches get it; Qt then takes the svg
#    format from our plugin and never loads the system libqsvg.so.
install -d "$envdir"
cat > "$envfile" <<EOF
# Added by svg-icon-renderer/install.sh. Delete this file (or run undo.sh) to go back to QtSvg.
export QT_PLUGIN_PATH="$dest\${QT_PLUGIN_PATH:+:\$QT_PLUGIN_PATH}"
EOF

# 3. drop KDE's icon cache so icons drawn by QtSvg are redrawn (it's rebuilt automatically)
rm -f "$HOME/.cache/icon-cache.kcache"

echo "Installed $dest/imageformats/librsvgqt.so"
echo "Session setting: $envfile"
echo "Log out and back in to switch Plasma over."
