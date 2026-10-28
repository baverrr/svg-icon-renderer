#!/bin/bash
# Opens a Dolphin window on a folder whose icon is test/filter-test.svg and screenshots it.
#   bash dolphin-test.sh before   -> Dolphin as it is (QtSvg)       -> test/screenshots/before.png
#   bash dolphin-test.sh after    -> Dolphin with the built plugin  -> test/screenshots/after.png
# The test Dolphin gets its own config and cache folders, so your Dolphin settings and KDE's
# icon cache aren't touched, and a cached QtSvg icon can't leak into the "after" shot.
set -euo pipefail
here=$(dirname "$(readlink -f "$0")")
mode=${1:?usage: dolphin-test.sh before|after}
work="$here/../build/dolphin-test"
shots="$here/screenshots"

rm -rf "$work/$mode"
mkdir -p "$work/$mode/config" "$work/$mode/cache" "$work/folders/Filter test" "$shots"
printf '[Desktop Entry]\nIcon=%s\n' "$here/filter-test.svg" > "$work/folders/Filter test/.directory"
# Keep the colour scheme and fonts; make the icons big enough to see the effects.
cp "$HOME/.config/kdeglobals" "$work/$mode/config/" 2>/dev/null || true
printf '[IconsMode]\nIconSize=256\nPreviewSize=256\n\n[General]\nShowFullPath=true\n' > "$work/$mode/config/dolphinrc"

env_args=(XDG_CONFIG_HOME="$work/$mode/config" XDG_CACHE_HOME="$work/$mode/cache")
if [ "$mode" = after ]; then
  plugin_dir="$here/../build"
  [ -f "$plugin_dir/imageformats/librsvgqt.so" ] || { echo "Build the plugin first (build.sh)."; exit 1; }
  env_args+=(QT_PLUGIN_PATH="$(readlink -f "$plugin_dir")")
else
  env_args+=(QT_PLUGIN_PATH=)
fi

env "${env_args[@]}" dolphin --new-window "$work/folders" >/dev/null 2>&1 &
pid=$!
sleep 4
# Record which SVG plugin that Dolphin process actually loaded.
awk '{ $1=$2=$3=$4=$5=""; sub(/^ +/, "") } /imageformats\/[^/]*svg[^/]*\.so$/' "/proc/$pid/maps" | sort -u | sed 's/^/Dolphin loaded: /' || echo "Dolphin loaded no svg plugin"
spectacle -b -n -a -o "$shots/$mode.png"
sleep 1
kill "$pid" 2>/dev/null || true
echo "Saved $shots/$mode.png"
