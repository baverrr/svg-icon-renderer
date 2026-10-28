#!/bin/bash
# Builds build/imageformats/librsvgqt.so, the librsvg-backed Qt 6 svg/svgz image plugin.
# Needs: sudo apt install qt6-base-dev librsvg2-dev libcairo2-dev pkgconf
# Run: bash build.sh
set -euo pipefail
here=$(dirname "$(readlink -f "$0")")
out="$here/build"
moc=/usr/lib/qt6/libexec/moc

missing=()
for pkg in qt6-base-dev librsvg2-dev libcairo2-dev pkgconf; do
  dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "Missing build packages. Install them with:"
  echo "  sudo apt install ${missing[*]}"
  exit 1
fi

mkdir -p "$out/imageformats"
# shellcheck disable=SC2046
"$moc" $(pkg-config --cflags-only-I Qt6Gui) "$here/src/rsvgplugin.h" -o "$out/moc_rsvgplugin.cpp"

# shellcheck disable=SC2046
g++ -std=c++17 -O2 -fPIC -shared -Wall -Wextra -DQT_NO_KEYWORDS -DQT_NO_DEBUG \
  -fvisibility=hidden -Wl,--no-undefined -Wl,-z,defs \
  -I"$here/src" \
  $(pkg-config --cflags Qt6Gui librsvg-2.0 cairo) \
  "$here/src/rsvgplugin.cpp" "$out/moc_rsvgplugin.cpp" \
  -o "$out/imageformats/librsvgqt.so" \
  $(pkg-config --libs Qt6Gui librsvg-2.0 cairo)

echo "Built $out/imageformats/librsvgqt.so"
